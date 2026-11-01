"""Bounded, tenant-authenticated voice downloads and original-language transcription.

Audio bytes exist only in worker memory; only the reviewable transcript is saved.
"""

import hashlib
import io
import re
import time
import wave
from urllib.parse import urlsplit

import av
import httpx
from fastapi import HTTPException

from .config import has_real_config, settings
from .meta_signup import decrypt_token

MAX_AUDIO_BYTES = 8 * 1024 * 1024
MAX_AUDIO_SECONDS = 180
AUDIO_FORMATS = {
    "audio/ogg": "ogg",
    "audio/opus": "ogg",
    "audio/mpeg": "mp3",
    "audio/mp4": "mov",
    "audio/aac": "aac",
    "audio/amr": "amr",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/webm": "webm",
}


class VoiceError(Exception):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


def voice_ready():
    return (
        settings.voice_transcription_enabled
        and settings.ai_provider == "openai"
        and has_real_config(settings.openai_api_key.get_secret_value())
        and bool(settings.openai_transcription_model.strip())
    )


def media_client():
    return httpx.Client(timeout=httpx.Timeout(30, connect=5), follow_redirects=False)


def transcription_client():
    return httpx.Client(timeout=httpx.Timeout(60, connect=5), follow_redirects=False)


def download_audio(message, phone, *, kind="audio"):
    # Never borrow another workspace's token, even when using a legacy test number.
    if (
        phone.organization_id != message.organization_id
        or phone.phone_number_id != message.phone_number_id
    ):
        raise VoiceError("Voice message does not belong to this connection")
    try:
        token = (
            decrypt_token(phone.access_token_encrypted)
            if phone.access_token_encrypted
            else ""
        )
    except HTTPException as exc:
        raise VoiceError(
            "WhatsApp voice credentials need administrator attention"
        ) from exc
    if not token and phone.phone_number_id == settings.whatsapp_phone_number_id:
        token = settings.whatsapp_access_token.get_secret_value()
    if not token or not re.fullmatch(r"\d{1,128}", message.media_id):
        raise VoiceError("Voice download needs an active WhatsApp connection")
    version = settings.whatsapp_graph_api_version
    if not re.fullmatch(r"v\d+\.\d+", version):
        raise VoiceError("WhatsApp API version is not configured")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        with media_client() as client:
            response = client.get(
                f"https://graph.facebook.com/{version}/{message.media_id}",
                params={"phone_number_id": phone.phone_number_id},
                headers=headers,
            )
            response.raise_for_status()
            meta = response.json()
            if not isinstance(meta, dict) or str(meta.get("id")) != message.media_id:
                raise VoiceError("WhatsApp returned invalid voice metadata")
            url = meta.get("url", "")
            parsed = urlsplit(url)
            if (
                parsed.scheme != "https"
                or parsed.hostname != "lookaside.fbsbx.com"
                or parsed.port not in (None, 443)
                or parsed.username
                or parsed.password
                or parsed.fragment
            ):
                raise VoiceError("WhatsApp returned an untrusted voice download URL")
            mime = str(meta.get("mime_type", "")).split(";")[0].strip().lower()
            allowed = (
                {"image/jpeg", "image/png", "image/webp"}
                if kind == "image"
                else AUDIO_FORMATS
            )
            if mime not in allowed:
                raise VoiceError("Voice audio format is not supported")
            size = meta.get("file_size")
            if type(size) is not int or not 0 < size <= MAX_AUDIO_BYTES:
                raise VoiceError("Voice notes must be no larger than 8 MB")
            checksum = meta.get("sha256", "")
            if not isinstance(checksum, str) or not re.fullmatch(
                r"[a-fA-F0-9]{64}", checksum
            ):
                raise VoiceError("Voice download has no valid integrity checksum")
            if (
                message.media_sha256
                and message.media_sha256.lower() != checksum.lower()
            ):
                raise VoiceError("Voice metadata checksum does not match the message")
            raw = bytearray()
            started = time.monotonic()
            with client.stream("GET", url, headers=headers) as media:
                media.raise_for_status()
                for chunk in media.iter_bytes(65536):
                    raw.extend(chunk)
                    if len(raw) > MAX_AUDIO_BYTES or time.monotonic() - started > 40:
                        raise VoiceError(
                            "Voice download exceeded its size or time limit"
                        )
            if len(raw) != size or hashlib.sha256(raw).hexdigest() != checksum.lower():
                raise VoiceError("Voice download failed its integrity check")
            return bytes(raw), mime
    except VoiceError:
        raise
    except httpx.HTTPStatusError as exc:
        raise VoiceError(
            "WhatsApp voice download is unavailable",
            exc.response.status_code == 429 or exc.response.status_code >= 500,
        ) from exc
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        raise VoiceError("WhatsApp voice download is unavailable", True) from exc


def audio_to_wav(raw, mime):
    if not raw or len(raw) > MAX_AUDIO_BYTES or mime not in AUDIO_FORMATS:
        raise VoiceError("Voice audio format or size is not supported")
    output = io.BytesIO()
    samples = 0
    started = time.monotonic()
    try:
        with av.open(
            io.BytesIO(raw),
            format=AUDIO_FORMATS[mime],
            mode="r",
            options={"protocol_whitelist": "pipe"},
        ) as source:
            if not source.streams.audio:
                raise VoiceError("Voice attachment has no audio stream")
            resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
            with wave.open(output, "wb") as target:
                target.setnchannels(1)
                target.setsampwidth(2)
                target.setframerate(16000)
                for frame in source.decode(audio=0):
                    if time.monotonic() - started > 25:
                        raise VoiceError("Voice decoding exceeded its time limit")
                    for converted in resampler.resample(frame):
                        samples += converted.samples
                        if samples > MAX_AUDIO_SECONDS * 16000:
                            raise VoiceError(
                                "Voice notes must be no longer than 3 minutes"
                            )
                        target.writeframesraw(
                            bytes(converted.planes[0])[: converted.samples * 2]
                        )
                for converted in resampler.resample(None):
                    samples += converted.samples
                    if samples > MAX_AUDIO_SECONDS * 16000:
                        raise VoiceError("Voice notes must be no longer than 3 minutes")
                    target.writeframesraw(
                        bytes(converted.planes[0])[: converted.samples * 2]
                    )
        if samples < 1600:
            raise VoiceError("Voice note is empty or too short to transcribe")
        return output.getvalue()
    except VoiceError:
        raise
    except (av.error.FFmpegError, ValueError, EOFError, OverflowError) as exc:
        raise VoiceError("Voice attachment could not be decoded") from exc


def transcribe_audio(raw, mime):
    if not voice_ready():
        raise VoiceError("Voice transcription is not configured")
    audio = audio_to_wav(raw, mime)
    try:
        with transcription_client() as client:
            response = client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key.get_secret_value()}"
                },
                data={
                    "model": settings.openai_transcription_model,
                    "response_format": "json",
                    "prompt": "Transcribe only audible speech in its original Sinhala, English or Tamil, preserving mixed languages. Do not translate or invent words. Silence must remain empty.",
                },
                files={"file": ("voice.wav", audio, "audio/wav")},
            )
            response.raise_for_status()
            result = response.json()
        text = result.get("text") if isinstance(result, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise VoiceError(
                "No clear speech detected; review the voice message manually"
            )
        if len(text) > 10000:
            raise VoiceError("Voice transcript is too long; review manually")
        return text.strip()
    except VoiceError:
        raise
    except httpx.HTTPStatusError as exc:
        try:
            error = exc.response.json().get("error", {})
        except (ValueError, AttributeError):
            error = {}
        if isinstance(error, dict) and (
            error.get("code") in {"credit_balance_exhausted", "insufficient_quota"}
            or error.get("type") == "insufficient_quota"
        ):
            raise VoiceError(
                "OpenAI API credits are unavailable; ask your administrator to add credits"
            ) from exc
        raise VoiceError(
            "Speech transcription provider is unavailable",
            exc.response.status_code == 429 or exc.response.status_code >= 500,
        ) from exc
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise VoiceError("Speech transcription provider is unavailable", True) from exc
