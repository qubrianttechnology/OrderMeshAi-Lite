import hashlib
import io
import wave
from types import SimpleNamespace

import av
import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app import voice, whatsapp
from app.config import settings
from app.extraction import LocalExtractor
from app.models import ExtractionDraft, WhatsAppMessage, WhatsAppWebhookEvent

from .conftest import catalog, register
from .test_whatsapp import connect_phone, payload, signed_post


def wav_bytes():
    target = io.BytesIO()
    with wave.open(target, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(b"\0\0" * 8000)
    return target.getvalue()


def configure(monkeypatch, transcript, metadata_changes=None, transcription_status=200):
    raw = wav_bytes()
    requests = []
    monkeypatch.setattr(settings, "ai_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", SecretStr("test-speech-key"))
    monkeypatch.setattr(settings, "voice_transcription_enabled", True)
    monkeypatch.setattr(
        settings, "whatsapp_access_token", SecretStr("test-media-token")
    )
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "123456789012345")
    monkeypatch.setattr(settings, "whatsapp_graph_api_version", "v26.0")
    monkeypatch.setattr(whatsapp, "get_extractor", lambda: LocalExtractor())

    def media_handler(request):
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer test-media-token"
        if request.url.host == "graph.facebook.com":
            assert request.url.params["phone_number_id"] == "123456789012345"
            return httpx.Response(
                200,
                json={
                    "id": "12345",
                    "url": "https://lookaside.fbsbx.com/whatsapp_business/attachments/?id=12345",
                    "file_size": len(raw),
                    "mime_type": "audio/wav",
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    **(metadata_changes or {}),
                },
            )
        return httpx.Response(200, content=raw)

    def speech_handler(request):
        requests.append(request)
        assert request.url == "https://api.openai.com/v1/audio/transcriptions"
        assert request.headers["Authorization"] == "Bearer test-speech-key"
        assert b'filename="voice.wav"' in request.content
        assert b"gpt-transcribe" in request.content
        return httpx.Response(transcription_status, json={"text": transcript})

    monkeypatch.setattr(
        voice,
        "media_client",
        lambda: httpx.Client(transport=httpx.MockTransport(media_handler)),
    )
    monkeypatch.setattr(
        voice,
        "transcription_client",
        lambda: httpx.Client(transport=httpx.MockTransport(speech_handler)),
    )
    return requests


def audio_payload():
    data = payload()
    incoming = data["entry"][0]["changes"][0]["value"]["messages"][0]
    incoming.pop("text")
    incoming.update(type="audio", audio={"id": "12345", "mime_type": "audio/wav"})
    return data


@pytest.mark.parametrize("transcript", ["Rice 2", "සහල් 2", "அரிசி 2"])
def test_voice_note_becomes_reviewable_draft_without_order(
    setup, monkeypatch, transcript
):
    client, factory = setup
    register(client)
    _, product = catalog(client)
    client.put(
        f"/api/products/{product['id']}",
        json={
            "name": "Rice",
            "sku": "RICE-1",
            "price_minor": 25000,
            "aliases": ["සහල්", "அரிசி"],
        },
    )
    connect_phone(client)
    monkeypatch.setattr(settings, "meta_app_secret", SecretStr("test-meta-secret"))
    requests = configure(monkeypatch, transcript)
    assert signed_post(client, audio_payload()).json()["queued"] == 1
    assert signed_post(client, audio_payload()).json()["queued"] == 0
    with factory() as db:
        event = db.scalar(select(WhatsAppWebhookEvent))
        assert whatsapp._process_event(db, event.organization_id, event.id, 0)
        message = db.scalar(select(WhatsAppMessage))
        draft = db.scalar(select(ExtractionDraft))
        assert message.text == transcript
        assert message.transcription_status == "transcribed"
        assert draft.result["requires_confirmation"]
        assert draft.result["items"][0]["quantity"] == 2
        assert draft.result["items"][0]["product_id"] == product["id"]
        assert "voice_transcript_requires_review" in draft.result["flags"]
        conversation_id = message.conversation_id
    assert client.get("/api/orders").json() == []
    messages = client.get(f"/api/inbox/conversations/{conversation_id}/messages").json()
    assert messages[0]["transcription_status"] == "transcribed"
    assert "media_id" not in messages[0]
    assert len(requests) == 3


@pytest.mark.parametrize(
    "metadata,reason",
    [
        ({"url": "https://evil.example/audio"}, "untrusted"),
        ({"url": "https://lookaside.fbsbx.com.evil.example/audio"}, "untrusted"),
        ({"url": "http://127.0.0.1/audio"}, "untrusted"),
        ({"file_size": voice.MAX_AUDIO_BYTES + 1}, "8 MB"),
        ({"mime_type": "text/html"}, "format"),
        ({"sha256": "0" * 64}, "integrity"),
    ],
)
def test_media_is_bounded_and_does_not_forward_token_to_untrusted_hosts(
    monkeypatch, metadata, reason
):
    requests = configure(monkeypatch, "Rice 2", metadata)
    message = SimpleNamespace(
        organization_id="a",
        phone_number_id="123456789012345",
        media_id="12345",
        media_sha256="",
    )
    phone = SimpleNamespace(
        organization_id="a",
        phone_number_id="123456789012345",
        access_token_encrypted="",
    )
    with pytest.raises(voice.VoiceError, match=reason):
        voice.download_audio(message, phone)
    assert all(
        request.url.host in {"graph.facebook.com", "lookaside.fbsbx.com"}
        for request in requests
    )
    assert not any(request.url.host == "api.openai.com" for request in requests)


def test_cross_tenant_audio_cannot_use_another_connection(monkeypatch):
    requests = configure(monkeypatch, "Rice 2")
    with pytest.raises(voice.VoiceError, match="does not belong"):
        voice.download_audio(
            SimpleNamespace(organization_id="a"), SimpleNamespace(organization_id="b")
        )
    assert requests == []


def test_empty_and_invalid_audio_are_not_invented(monkeypatch):
    configure(monkeypatch, "   ")
    with pytest.raises(voice.VoiceError, match="No clear speech"):
        voice.transcribe_audio(wav_bytes(), "audio/wav")
    with pytest.raises(voice.VoiceError, match="could not be decoded"):
        voice.audio_to_wav(b"not-a-real-audio-file", "audio/ogg")
    monkeypatch.setattr(voice, "MAX_AUDIO_SECONDS", 0)
    with pytest.raises(voice.VoiceError, match="3 minutes"):
        voice.audio_to_wav(wav_bytes(), "audio/wav")


def test_ogg_opus_voice_note_decodes_to_wav():
    output = io.BytesIO()
    with av.open(io.BytesIO(wav_bytes()), mode="r", format="wav") as source:
        with av.open(output, mode="w", format="ogg") as target:
            stream = target.add_stream("libopus", rate=48000)
            stream.layout = "mono"
            resampler = av.AudioResampler(format="flt", layout="mono", rate=48000)
            for frame in source.decode(audio=0):
                for converted in resampler.resample(frame):
                    for packet in stream.encode(converted):
                        target.mux(packet)
            for converted in resampler.resample(None):
                for packet in stream.encode(converted):
                    target.mux(packet)
            for packet in stream.encode(None):
                target.mux(packet)
    wav = voice.audio_to_wav(output.getvalue(), "audio/ogg")
    with wave.open(io.BytesIO(wav)) as decoded:
        assert decoded.getnchannels() == 1
        assert decoded.getframerate() == 16000
        assert decoded.getnframes() > 1600


def test_disabled_voice_is_visible_and_can_be_retried_only_by_own_tenant(
    setup, monkeypatch
):
    client, factory = setup
    register(client)
    connect_phone(client)
    monkeypatch.setattr(settings, "meta_app_secret", SecretStr("test-meta-secret"))
    requests = configure(monkeypatch, "Rice 2")
    monkeypatch.setattr(settings, "voice_transcription_enabled", False)
    signed_post(client, audio_payload())
    with factory() as db:
        event = db.scalar(select(WhatsAppWebhookEvent))
        assert whatsapp._process_event(db, event.organization_id, event.id, 0)
        message = db.scalar(select(WhatsAppMessage))
        message_id = message.id
        assert message.transcription_status == "failed"
        assert "not configured" in message.transcription_error
    assert requests == []
    url = f"/api/inbox/messages/{message_id}/transcription/retry"
    assert client.post(url).status_code == 503
    monkeypatch.setattr(settings, "voice_transcription_enabled", True)
    assert client.post(url).status_code == 200
    register(client, "other")
    assert client.post(url).status_code == 404


def test_extraction_retry_does_not_transcribe_again(setup, monkeypatch):
    client, factory = setup
    register(client)
    catalog(client)
    connect_phone(client)
    monkeypatch.setattr(settings, "meta_app_secret", SecretStr("test-meta-secret"))
    requests = configure(monkeypatch, "Rice 2")

    class FailedExtractor:
        def extract(self, *args):
            raise whatsapp.ProviderUnavailable("test provider failure")

    monkeypatch.setattr(whatsapp, "get_extractor", lambda: FailedExtractor())
    signed_post(client, audio_payload())
    with factory() as db:
        event = db.scalar(select(WhatsAppWebhookEvent))
        assert not whatsapp._process_event(db, event.organization_id, event.id, 0)
        assert db.scalar(select(WhatsAppMessage)).text == "Rice 2"
        event.claimed_at = None
        db.commit()
        monkeypatch.setattr(whatsapp, "get_extractor", lambda: LocalExtractor())
        assert whatsapp._process_event(db, event.organization_id, event.id, 1)
        assert db.scalar(select(ExtractionDraft))
    assert len(requests) == 3


def test_exhausted_quota_is_actionable_and_does_not_automatically_retry(monkeypatch):
    configure(monkeypatch, "Rice 2")

    def quota(request):
        return httpx.Response(
            429,
            json={
                "error": {
                    "code": "credit_balance_exhausted",
                    "type": "insufficient_quota",
                }
            },
        )

    monkeypatch.setattr(
        voice,
        "transcription_client",
        lambda: httpx.Client(transport=httpx.MockTransport(quota)),
    )
    with pytest.raises(voice.VoiceError, match="credits are unavailable") as error:
        voice.transcribe_audio(wav_bytes(), "audio/wav")
    assert not error.value.retryable
