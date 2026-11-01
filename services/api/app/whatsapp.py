import asyncio
import hashlib
import hmac
import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from .ai_provider import ProviderUnavailable, get_extractor
from .automation import bot_settings, process_bot_replies_once, queue_inbound_reply
from .business import classify_message
from .config import has_real_config, settings
from .db import SessionLocal, get_db
from .extraction import LocalExtractor
from .image_extraction import ImageError, image_flags, image_ready, read_image
from .meta_signup import decrypt_token
from .models import (
    Customer,
    CustomerWhatsAppContact,
    ExtractionDraft,
    Organization,
    Product,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppPhoneNumber,
    WhatsAppWebhookEvent,
    as_utc,
    now,
)
from .schemas import (
    StrictModel,
    WhatsAppConversationCustomerInput,
    WhatsAppPhoneNumberInput,
    WhatsAppReplyInput,
    WhatsAppSimulatorInput,
)
from .security import Tenant, require, subscription_access, tenant_context
from .service_requests import extract_service_request, uses_service_workflow
from .voice import VoiceError, download_audio, transcribe_audio, voice_ready

logger = logging.getLogger("ordermesh.whatsapp")
router = APIRouter()
MAX_WEBHOOK_BYTES = 1_000_000
MAX_ATTEMPTS = 5
MESSAGE_WINDOW = timedelta(hours=24)
DELIVERY_RANK = {"accepted": 0, "sent": 1, "delivered": 2, "read": 3, "failed": 4}


class WhatsAppProviderError(Exception):
    def __init__(self, status_code: int):
        self.status_code = status_code


def _normalize_phone(value: str) -> str:
    normalized = re.sub(r"[\s().-]", "", value)
    if not re.fullmatch(r"\+?[1-9]\d{7,14}", normalized):
        raise ValueError("Invalid international phone number")
    return normalized.lstrip("+")


def _meta_client():
    return httpx.Client(timeout=httpx.Timeout(15, connect=5))


def _send_meta_text(
    recipient: str,
    message: str,
    *,
    token_override: str | None = None,
    phone_override: str | None = None,
) -> str:
    token = token_override or settings.whatsapp_access_token.get_secret_value()
    phone_number_id = phone_override or settings.whatsapp_phone_number_id
    version = settings.whatsapp_graph_api_version
    if (
        not has_real_config(token)
        or not phone_number_id
        or not re.fullmatch(r"v\d+\.\d+", version)
    ):
        raise HTTPException(503, "WhatsApp Cloud API is not configured")
    if not re.fullmatch(r"\d{5,128}", phone_number_id):
        raise HTTPException(503, "WhatsApp Cloud API is not configured")
    endpoint = f"https://graph.facebook.com/{version}/{phone_number_id}/messages"
    try:
        with _meta_client() as client:
            response = client.post(
                endpoint,
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": recipient,
                    "type": "text",
                    "text": {"preview_url": False, "body": message},
                },
            )
            if response.status_code == 429:
                raise WhatsAppProviderError(429)
            response.raise_for_status()
            payload = response.json()
    except WhatsAppProviderError as exc:
        raise HTTPException(
            exc.status_code, "WhatsApp provider rate limit reached"
        ) from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(
            504, "WhatsApp provider timed out; delivery is unknown"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(502, "WhatsApp provider rejected the message") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "WhatsApp provider is unavailable") from exc
    messages = payload.get("messages") if isinstance(payload, dict) else None
    external_id = (
        messages[0].get("id")
        if isinstance(messages, list) and messages and isinstance(messages[0], dict)
        else None
    )
    if not isinstance(external_id, str) or not external_id or len(external_id) > 256:
        raise HTTPException(502, "WhatsApp provider returned an invalid response")
    return external_id


def _signature_valid(raw: bytes, signature: str | None) -> bool:
    secret = settings.meta_app_secret.get_secret_value()
    if not secret or not signature or not signature.startswith("sha256="):
        return False
    supplied = signature[7:]
    if len(supplied) != 64 or not supplied.isascii():
        return False
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied)


def _timestamp(value: str) -> datetime:
    try:
        return datetime.fromtimestamp(int(value), timezone.utc)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Invalid WhatsApp message timestamp") from exc


def _customer_match(db: DBSession, organization_id: str, phone: str):
    """Return only deterministic customer matches for a WhatsApp sender.

    WhatsApp profile names are sender-controlled and are never used for
    matching. A saved WhatsApp identity has precedence. As a migration path,
    one active customer whose general phone is the same valid international
    number is accepted; ambiguous or local-format records remain unassigned.
    """
    contact = db.scalar(
        select(CustomerWhatsAppContact).where(
            CustomerWhatsAppContact.organization_id == organization_id,
            CustomerWhatsAppContact.phone == phone,
        )
    )
    if contact:
        customer = db.scalar(
            select(Customer).where(
                Customer.organization_id == organization_id,
                Customer.id == contact.customer_id,
                Customer.active.is_(True),
            )
        )
        if customer:
            return customer, "whatsapp_contact"

    candidates = []
    for customer in db.scalars(
        select(Customer).where(
            Customer.organization_id == organization_id,
            Customer.active.is_(True),
        )
    ):
        try:
            if customer.phone and _normalize_phone(customer.phone) == phone:
                candidates.append(customer)
        except ValueError:
            continue
    return (
        (candidates[0], "customer_phone")
        if len(candidates) == 1
        else (None, "unmatched")
    )


def _queue_message(db: DBSession, message: dict) -> bool:
    phone_number_id = message.get("phone_number_id")
    external_id = message.get("id")
    customer_phone = message.get("from")
    if not all(
        isinstance(value, str) and value and len(value) <= limit
        for value, limit in (
            (phone_number_id, 128),
            (external_id, 256),
            (customer_phone, 40),
        )
    ):
        raise ValueError("Invalid WhatsApp message identifiers")
    try:
        customer_phone = _normalize_phone(customer_phone)
    except ValueError as exc:
        raise ValueError("Invalid WhatsApp sender phone number") from exc
    message_type = message.get("type", "unknown")
    if not isinstance(message_type, str) or len(message_type) > 20:
        raise ValueError("Invalid WhatsApp message type")
    message_text = None
    if message_type == "text":
        text_content = message.get("text")
        message_text = (
            text_content.get("body") if isinstance(text_content, dict) else None
        )
        if not isinstance(message_text, str) or not message_text.strip():
            raise ValueError("Invalid WhatsApp text message")
        if len(message_text) > 10000:
            raise ValueError("WhatsApp message is too long")

    phone = db.scalar(
        select(WhatsAppPhoneNumber).where(
            WhatsAppPhoneNumber.phone_number_id == phone_number_id,
            WhatsAppPhoneNumber.active.is_(True),
        )
    )
    if not phone:
        raise LookupError("WhatsApp phone number is not registered")
    if db.scalar(
        select(WhatsAppMessage.id).where(WhatsAppMessage.external_id == external_id)
    ):
        return False

    contacts = message.get("_contact", {})
    profile = contacts.get("profile", {}) if isinstance(contacts, dict) else {}
    customer_name = profile.get("name", "") if isinstance(profile, dict) else ""
    if not isinstance(customer_name, str):
        customer_name = ""
    customer_name = customer_name[:120]
    sent_at = _timestamp(message.get("timestamp"))
    if db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT set_config('app.organization_id', :tenant, true)"),
            {"tenant": phone.organization_id},
        )
    matched_customer, match_source = _customer_match(
        db, phone.organization_id, customer_phone
    )
    conversation = db.scalar(
        select(WhatsAppConversation).where(
            WhatsAppConversation.organization_id == phone.organization_id,
            WhatsAppConversation.phone_number_id == phone_number_id,
            WhatsAppConversation.customer_phone == customer_phone,
        )
    )
    if conversation is None:
        conversation = WhatsAppConversation(
            organization_id=phone.organization_id,
            phone_number_id=phone_number_id,
            customer_phone=customer_phone,
            customer_name=(
                matched_customer.name if matched_customer else customer_name
            ),
            customer_id=matched_customer.id if matched_customer else None,
            customer_match_source=match_source,
            last_message_preview=(message_text or f"{message_type} message")[:500],
            last_message_at=sent_at,
            unread_count=1,
        )
        db.add(conversation)
        db.flush()
    else:
        if matched_customer:
            conversation.customer_id = matched_customer.id
            conversation.customer_name = matched_customer.name
            conversation.customer_match_source = match_source
        elif not conversation.customer_id:
            conversation.customer_name = customer_name or conversation.customer_name
            conversation.customer_match_source = "unmatched"
        conversation.last_message_preview = (message_text or f"{message_type} message")[
            :500
        ]
        conversation.last_message_at = sent_at
        conversation.unread_count += 1
        conversation.archived = False

    media = message.get(message_type, {}) if message_type in {"audio", "image"} else {}
    if not isinstance(media, dict):
        media = {}
    media_id = media.get("id", "")
    media_id = (
        media_id
        if isinstance(media_id, str) and re.fullmatch(r"\d{1,128}", media_id)
        else ""
    )
    mime = media.get("mime_type", "")
    mime = mime[:100] if isinstance(mime, str) else ""
    checksum = media.get("sha256", "")
    checksum = (
        checksum
        if isinstance(checksum, str) and re.fullmatch(r"[a-fA-F0-9]{64}", checksum)
        else ""
    )
    stored = WhatsAppMessage(
        organization_id=phone.organization_id,
        conversation_id=conversation.id,
        phone_number_id=phone_number_id,
        external_id=external_id,
        direction="inbound",
        message_type=message_type,
        text=message_text,
        media_caption=str(media.get("caption", ""))[:1024]
        if isinstance(media.get("caption", ""), str)
        else "",
        media_id=media_id,
        media_mime_type=mime,
        media_sha256=checksum,
        transcription_status="pending" if message_type in {"audio", "image"} else "",
        customer_phone=customer_phone,
        customer_name=customer_name,
        sent_at=sent_at,
    )
    db.add(stored)
    db.flush()
    db.add(
        WhatsAppWebhookEvent(
            organization_id=phone.organization_id,
            external_id=external_id,
            message_id=stored.id,
        )
    )
    return True


def _transcribe_inbound_message(db: DBSession, event: WhatsAppWebhookEvent):
    message = db.scalar(
        select(WhatsAppMessage).where(
            WhatsAppMessage.organization_id == event.organization_id,
            WhatsAppMessage.id == event.message_id,
        )
    )
    if not message or message.message_type not in {"audio", "image"} or message.text:
        return
    phone = db.scalar(
        select(WhatsAppPhoneNumber).where(
            WhatsAppPhoneNumber.organization_id == event.organization_id,
            WhatsAppPhoneNumber.phone_number_id == message.phone_number_id,
            WhatsAppPhoneNumber.active.is_(True),
        )
    )
    error = None
    try:
        local_org = db.get(Organization, event.organization_id)
        if local_org and bot_settings(local_org)["enabled"]:
            raise VoiceError(
                "Local chatbot mode needs manual review of audio and images; external AI media reading is disabled for this WhatsApp workflow"
            )
        if message.message_type == "image" and not image_ready():
            raise ImageError(
                "Image extraction is not configured; ask your administrator"
            )
        if message.message_type == "audio" and not voice_ready():
            raise VoiceError(
                "Voice transcription is not configured; ask your administrator"
            )
        org = db.get(Organization, event.organization_id)
        if not org or not subscription_access(org):
            raise VoiceError(
                "Subscription expired; renew before transcribing voice notes"
            )
        if not phone:
            raise VoiceError("Voice download needs an active WhatsApp connection")
        if message.message_type == "image":
            raw, _mime = download_audio(message, phone, kind="image")
            readout = read_image(raw)
            message.media_uncertain = readout.uncertain
            source_text = "\n".join(
                part for part in [message.media_caption, readout.text] if part
            ).strip()
            if not source_text:
                raise ImageError(
                    "No readable order text in the image; enter details manually"
                )
            if len(source_text) > 10000:
                raise ImageError("Image text is too long; crop it to the order details")
            message.text = source_text
        else:
            raw, mime = download_audio(message, phone)
            message.text = transcribe_audio(raw, mime)
        message.transcription_status = "transcribed"
        message.transcription_error = ""
        # This is only a preview; ordering remains tied to the original sender timestamp.
        conversation = db.scalar(
            select(WhatsAppConversation).where(
                WhatsAppConversation.organization_id == event.organization_id,
                WhatsAppConversation.id == message.conversation_id,
            )
        )
        if conversation and as_utc(conversation.last_message_at) == as_utc(
            message.sent_at
        ):
            conversation.last_message_preview = message.text[:500]
    except (VoiceError, ImageError) as exc:
        error = exc
        message.transcription_status = "pending" if exc.retryable else "failed"
        message.transcription_error = (
            str(exc).replace("Voice", "Image").replace("voice", "image")
            if message.message_type == "image"
            else str(exc)
        )[:240]
        message.category = "needs_review"
        message.category_reason = (
            "Image reading needs attention"
            if message.message_type == "image"
            else "Voice transcription needs attention"
        )
    message.updated_at = now()
    # Save transcription separately: a later extraction retry must not pay to
    # download/transcribe the same voice note again.
    db.commit()
    if db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT set_config('app.organization_id', :tenant, true)"),
            {"tenant": event.organization_id},
        )
    if error and error.retryable:
        raise ProviderUnavailable("Voice transcription will be retried") from error


def _extract_inbound_message(db: DBSession, event: WhatsAppWebhookEvent) -> None:
    message = db.scalar(
        select(WhatsAppMessage).where(
            WhatsAppMessage.organization_id == event.organization_id,
            WhatsAppMessage.id == event.message_id,
        )
    )
    if (
        not message
        or message.message_type not in {"text", "audio", "image"}
        or not message.text
    ):
        if message:
            message.updated_at = now()
        event.status = "processed"
        event.processed_at = now()
        return
    phone = db.scalar(
        select(WhatsAppPhoneNumber).where(
            WhatsAppPhoneNumber.organization_id == event.organization_id,
            WhatsAppPhoneNumber.phone_number_id == message.phone_number_id,
        )
    )
    if not phone:
        raise LookupError("WhatsApp phone registration is unavailable")
    catalog = list(
        db.scalars(
            select(Product).where(
                Product.organization_id == event.organization_id,
                Product.active.is_(True),
            )
        )
    )
    org = db.get(Organization, event.organization_id)
    if not message.category_reviewed:
        message.category, message.category_reason = classify_message(
            message.text, catalog, org.business_profile or {}
        )
    service_workflow = uses_service_workflow(org, catalog, message.text)
    if (
        not service_workflow
        and message.category != "business_order"
        and queue_inbound_reply(db, message, org)
    ):
        event.status = "processed"
        event.processed_at = now()
        event.last_error = ""
        return
    eligible = message.category in (
        {"business_order", "business_inquiry", "support"}
        if service_workflow
        else {"business_order", "business_inquiry"}
    )
    if not eligible or not subscription_access(org):
        queue_inbound_reply(db, message, org)
        if message.category == "business_order":
            message.category = "needs_review"
            message.category_reason = (
                "Subscription expired; renew before creating a draft"
            )
        message.updated_at = now()
        event.status = "processed"
        event.processed_at = now()
        event.last_error = ""
        return
    if message.extraction_draft_id:
        queue_inbound_reply(
            db, message, org, db.get(ExtractionDraft, message.extraction_draft_id)
        )
        event.status = "processed"
        event.processed_at = now()
        return
    local_chatbot = bot_settings(org)["enabled"]
    if service_workflow:
        result = (
            extract_service_request(message.text, org, force_local=True)
            if local_chatbot
            else extract_service_request(message.text, org)
        )
    else:
        extractor = LocalExtractor() if local_chatbot else get_extractor()
        result = extractor.extract(message.text, "auto", catalog).model_dump()
    if message.message_type == "image":
        result = image_flags(result, message.media_uncertain)
    if message.message_type == "audio":
        result["flags"] = [*result.get("flags", []), "voice_transcript_requires_review"]
        result["source_type"] = "voice_transcript"
    draft = ExtractionDraft(
        organization_id=event.organization_id,
        source_text=message.text,
        result=result,
        created_by=phone.connected_by,
    )
    db.add(draft)
    db.flush()
    message.extraction_draft_id = draft.id
    queue_inbound_reply(db, message, org, draft)
    message.updated_at = now()
    event.status = "processed"
    event.processed_at = now()
    event.last_error = ""


def _process_event(
    db: DBSession, organization_id: str, event_id: str, expected_attempts: int
) -> bool:
    current = now()
    retry_delay = min(300, 2**expected_attempts)
    if db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT set_config('app.organization_id', :tenant, true)"),
            {"tenant": organization_id},
        )
    claimable = or_(
        and_(
            WhatsAppWebhookEvent.status == "queued",
            or_(
                WhatsAppWebhookEvent.claimed_at.is_(None),
                WhatsAppWebhookEvent.claimed_at
                <= current - timedelta(seconds=retry_delay),
            ),
        ),
        and_(
            WhatsAppWebhookEvent.status == "processing",
            WhatsAppWebhookEvent.claimed_at < current - timedelta(minutes=5),
        ),
    )
    claimed = db.execute(
        update(WhatsAppWebhookEvent)
        .where(
            WhatsAppWebhookEvent.organization_id == organization_id,
            WhatsAppWebhookEvent.id == event_id,
            WhatsAppWebhookEvent.attempts == expected_attempts,
            WhatsAppWebhookEvent.attempts < MAX_ATTEMPTS,
            claimable,
        )
        .execution_options(synchronize_session=False)
        .values(
            status="processing",
            claimed_at=current,
            attempts=WhatsAppWebhookEvent.attempts + 1,
        )
    )
    if claimed.rowcount != 1:
        db.rollback()
        return False
    db.commit()
    try:
        if db.bind.dialect.name == "postgresql":
            db.execute(
                text("SELECT set_config('app.organization_id', :tenant, true)"),
                {"tenant": organization_id},
            )
        event = db.scalar(
            select(WhatsAppWebhookEvent).where(
                WhatsAppWebhookEvent.organization_id == organization_id,
                WhatsAppWebhookEvent.id == event_id,
            )
        )
        if event:
            _transcribe_inbound_message(db, event)
            _extract_inbound_message(db, event)
            db.commit()
            return True
        return False
    except (ProviderUnavailable, NotImplementedError, LookupError, ValueError):
        db.rollback()
        if db.bind.dialect.name == "postgresql":
            db.execute(
                text("SELECT set_config('app.organization_id', :tenant, true)"),
                {"tenant": organization_id},
            )
        event = db.scalar(
            select(WhatsAppWebhookEvent).where(
                WhatsAppWebhookEvent.organization_id == organization_id,
                WhatsAppWebhookEvent.id == event_id,
            )
        )
        if event:
            event.status = "failed" if event.attempts >= MAX_ATTEMPTS else "queued"
            event.claimed_at = now()
            event.last_error = "Message could not be processed"
            if event.status == "failed":
                message = db.scalar(
                    select(WhatsAppMessage).where(
                        WhatsAppMessage.organization_id == organization_id,
                        WhatsAppMessage.id == event.message_id,
                    )
                )
                if (
                    message
                    and message.message_type in {"audio", "image"}
                    and not message.text
                ):
                    message.transcription_status = "failed"
                    message.transcription_error = "Media reading failed after retries; try again or review manually"
                    message.updated_at = now()
            db.commit()
        logger.warning("WhatsApp message processing attempt failed")
        return False
    except Exception:
        db.rollback()
        logger.exception("Unexpected WhatsApp queue processing failure")
        raise


def process_pending_once() -> int:
    processed = 0
    with SessionLocal() as db:
        organization_ids = db.scalars(
            select(WhatsAppPhoneNumber.organization_id).distinct()
        ).all()
        for organization_id in organization_ids:
            if db.bind.dialect.name == "postgresql":
                db.execute(
                    text("SELECT set_config('app.organization_id', :tenant, true)"),
                    {"tenant": organization_id},
                )
            current = now()
            exhausted = db.scalars(
                select(WhatsAppWebhookEvent).where(
                    WhatsAppWebhookEvent.organization_id == organization_id,
                    WhatsAppWebhookEvent.status == "processing",
                    WhatsAppWebhookEvent.attempts >= MAX_ATTEMPTS,
                    WhatsAppWebhookEvent.claimed_at < current - timedelta(minutes=5),
                )
            ).all()
            for event in exhausted:
                event.status = "failed"
                event.last_error = "Message could not be processed"
            if exhausted:
                db.commit()
                if db.bind.dialect.name == "postgresql":
                    db.execute(
                        text("SELECT set_config('app.organization_id', :tenant, true)"),
                        {"tenant": organization_id},
                    )
            queue = db.scalars(
                select(WhatsAppWebhookEvent)
                .where(
                    WhatsAppWebhookEvent.organization_id == organization_id,
                    WhatsAppWebhookEvent.attempts < MAX_ATTEMPTS,
                    or_(
                        WhatsAppWebhookEvent.status == "queued",
                        and_(
                            WhatsAppWebhookEvent.status == "processing",
                            WhatsAppWebhookEvent.claimed_at
                            < current - timedelta(minutes=5),
                        ),
                    ),
                )
                .order_by(WhatsAppWebhookEvent.created_at)
                .limit(20)
                .with_for_update(skip_locked=True)
            ).all()
            for event in queue:
                if _process_event(db, organization_id, event.id, event.attempts):
                    processed += 1
    return processed


async def whatsapp_worker():
    while True:
        try:
            await asyncio.to_thread(process_pending_once)
            await asyncio.to_thread(process_bot_replies_once)
        except Exception:
            logger.exception("WhatsApp worker iteration failed")
        await asyncio.sleep(2)


def _meta_messages(payload: dict):
    if payload.get("object") != "whatsapp_business_account":
        return
    entries = payload.get("entry", [])
    if not isinstance(entries, list):
        return
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        changes = entry.get("changes", [])
        if not isinstance(changes, list):
            continue
        for change in changes:
            if not isinstance(change, dict):
                continue
            value = change.get("value", {})
            if not isinstance(value, dict):
                continue
            metadata = value.get("metadata", {})
            phone_number_id = (
                metadata.get("phone_number_id") if isinstance(metadata, dict) else None
            )
            contact_items = value.get("contacts", [])
            if not isinstance(contact_items, list):
                contact_items = []
            contacts = {
                item.get("wa_id"): item
                for item in contact_items
                if isinstance(item, dict) and isinstance(item.get("wa_id"), str)
            }
            incoming_messages = value.get("messages", [])
            if not isinstance(incoming_messages, list):
                continue
            for incoming in incoming_messages:
                if not isinstance(incoming, dict):
                    continue
                message = dict(incoming)
                message["phone_number_id"] = phone_number_id
                message["_contact"] = contacts.get(message.get("from"), {})
                yield message


def _meta_statuses(payload: dict):
    if payload.get("object") != "whatsapp_business_account":
        return
    for entry in payload.get("entry", []):
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes", []):
            if not isinstance(change, dict):
                continue
            value = change.get("value", {})
            if not isinstance(value, dict):
                continue
            metadata = value.get("metadata", {})
            phone_number_id = (
                metadata.get("phone_number_id") if isinstance(metadata, dict) else None
            )
            statuses = value.get("statuses", [])
            if not isinstance(statuses, list):
                continue
            for status in statuses:
                if isinstance(status, dict):
                    yield {**status, "phone_number_id": phone_number_id}


def _apply_delivery_status(db: DBSession, status: dict) -> bool:
    external_id = status.get("id")
    phone_number_id = status.get("phone_number_id")
    status_name = status.get("status")
    if (
        not isinstance(external_id, str)
        or not external_id
        or len(external_id) > 256
        or not isinstance(phone_number_id, str)
        or not isinstance(status_name, str)
        or status_name not in ("sent", "delivered", "read", "failed")
    ):
        raise ValueError("Invalid WhatsApp delivery status")
    event_at = _timestamp(status.get("timestamp"))
    phone = db.scalar(
        select(WhatsAppPhoneNumber).where(
            WhatsAppPhoneNumber.phone_number_id == phone_number_id,
            WhatsAppPhoneNumber.active.is_(True),
        )
    )
    if not phone:
        return False
    if db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT set_config('app.organization_id', :tenant, true)"),
            {"tenant": phone.organization_id},
        )
    message = db.scalar(
        select(WhatsAppMessage)
        .where(
            WhatsAppMessage.organization_id == phone.organization_id,
            WhatsAppMessage.phone_number_id == phone_number_id,
            WhatsAppMessage.external_id == external_id,
            WhatsAppMessage.direction == "outbound",
        )
        .with_for_update()
    )
    if not message:
        return False
    existing_at = (
        as_utc(message.status_updated_at) if message.status_updated_at else None
    )
    current_status = message.delivery_status or "accepted"
    if existing_at and event_at < existing_at:
        return False
    if existing_at == event_at and DELIVERY_RANK[status_name] <= DELIVERY_RANK.get(
        current_status, 0
    ):
        return False
    if (
        existing_at
        and DELIVERY_RANK.get(current_status, 0) > DELIVERY_RANK[status_name]
    ):
        return False
    errors = status.get("errors", [])
    error = errors[0] if isinstance(errors, list) and errors else {}
    if not isinstance(error, dict):
        error = {}
    error_code = error.get("code", "")
    error_title = error.get("title", "")
    message.delivery_status = status_name
    message.status_updated_at = event_at
    message.delivery_error_code = str(error_code)[:40] if error_code else ""
    message.delivery_error_message = str(error_title)[:500] if error_title else ""
    message.updated_at = now()
    return True


@router.get("/webhooks/whatsapp")
def verify_webhook(
    mode: str = Query(alias="hub.mode"),
    verify_token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge"),
):
    expected = settings.whatsapp_verify_token.get_secret_value()
    if (
        not expected
        or mode != "subscribe"
        or not hmac.compare_digest(verify_token.encode(), expected.encode())
    ):
        raise HTTPException(403, "Webhook verification denied")
    return PlainTextResponse(challenge)


@router.post("/webhooks/whatsapp")
async def receive_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(None),
    db: DBSession = Depends(get_db),
):
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > MAX_WEBHOOK_BYTES:
            raise HTTPException(413, "Webhook payload is too large")
    body = bytes(raw)
    if not _signature_valid(body, x_hub_signature_256):
        raise HTTPException(403, "Invalid webhook signature")
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError("Invalid webhook body")
        messages = list(_meta_messages(payload) or [])
        statuses = list(_meta_statuses(payload) or [])
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise HTTPException(400, "Invalid webhook payload") from exc
    accepted = 0
    duplicate_response = None
    try:
        for message in messages:
            try:
                if _queue_message(db, message):
                    accepted += 1
            except LookupError:
                db.rollback()
                raise HTTPException(404, "WhatsApp phone number is not registered")
            except ValueError as exc:
                db.rollback()
                raise HTTPException(400, str(exc)) from exc
        db.commit()
    except IntegrityError:
        db.rollback()
        duplicate = all(
            db.scalar(
                select(WhatsAppMessage.id).where(
                    WhatsAppMessage.external_id == message.get("id")
                )
            )
            for message in messages
        )
        if duplicate:
            duplicate_response = {"status": "accepted", "duplicates": True}
        else:
            raise HTTPException(409, "Webhook event could not be persisted")
    for status in statuses:
        try:
            _apply_delivery_status(db, status)
        except (ValueError, LookupError) as exc:
            db.rollback()
            raise HTTPException(400, "Invalid delivery status event") from exc
    if statuses:
        db.commit()
    return duplicate_response or {"status": "accepted", "queued": accepted}


@router.post("/api/inbox/phone-numbers", status_code=201)
def register_phone_number(
    body: WhatsAppPhoneNumberInput,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    require(tenant, "owner", "admin")
    if settings.app_env == "production":
        raise HTTPException(
            403, "Use Connect WhatsApp to verify ownership of your number"
        )
    phone = WhatsAppPhoneNumber(
        organization_id=tenant.id,
        connected_by=tenant.user_id,
        **body.model_dump(),
    )
    db.add(phone)
    db.commit()
    return {
        "id": phone.id,
        "phone_number_id": phone.phone_number_id,
        "connection_kind": phone.connection_kind,
        "display_phone_number": phone.display_phone_number,
        "active": phone.active,
    }


@router.get("/api/inbox/phone-numbers")
def list_phone_numbers(
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    return [
        {
            "id": phone.id,
            "phone_number_id": phone.phone_number_id,
            "connection_kind": phone.connection_kind,
            "display_phone_number": phone.display_phone_number,
            "active": phone.active,
        }
        for phone in db.scalars(
            select(WhatsAppPhoneNumber)
            .where(WhatsAppPhoneNumber.organization_id == tenant.id)
            .order_by(WhatsAppPhoneNumber.created_at)
        )
    ]


@router.get("/api/inbox/integration-status")
def integration_status(
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    require(tenant, "owner", "admin")
    database_role = {
        "name": "local",
        "superuser": False,
        "bypasses_rls": False,
    }
    if db.bind.dialect.name == "postgresql":
        role = db.execute(
            text(
                "SELECT current_user, r.rolsuper, r.rolbypassrls "
                "FROM pg_roles r WHERE r.rolname = current_user"
            )
        ).one()
        database_role = {
            "name": role.current_user,
            "superuser": role.rolsuper,
            "bypasses_rls": role.rolbypassrls,
        }
    linked_sender = db.scalar(
        select(WhatsAppPhoneNumber.id)
        .where(
            WhatsAppPhoneNumber.organization_id == tenant.id,
            WhatsAppPhoneNumber.active.is_(True),
            WhatsAppPhoneNumber.access_token_encrypted != "",
        )
        .limit(1)
    )
    ai_configured = settings.ai_provider == "local" or bool(
        settings.openai_api_key.get_secret_value() and settings.openai_model
    )
    return {
        "database": {
            "backend": make_url(str(db.bind.url)).get_backend_name(),
            "role": database_role,
            "rls_required": db.bind.dialect.name == "postgresql",
        },
        "whatsapp": {
            "configured": bool(
                has_real_config(settings.whatsapp_verify_token.get_secret_value())
                and has_real_config(settings.meta_app_secret.get_secret_value())
            ),
            "cloud_send_configured": bool(
                (
                    linked_sender
                    or (
                        has_real_config(
                            settings.whatsapp_access_token.get_secret_value()
                        )
                        and settings.whatsapp_phone_number_id
                    )
                )
                and re.fullmatch(r"v\d+\.\d+", settings.whatsapp_graph_api_version)
            ),
            "test_mode": settings.whatsapp_test_mode,
            "callback_path": "/webhooks/whatsapp",
            "registered_phone_numbers": db.scalar(
                select(func.count(WhatsAppPhoneNumber.id)).where(
                    WhatsAppPhoneNumber.organization_id == tenant.id,
                    WhatsAppPhoneNumber.active.is_(True),
                )
            ),
        },
        "ai": {
            "provider": settings.ai_provider,
            "configured": ai_configured,
            "automatic_confirmation": False,
        },
    }


@router.put("/api/inbox/conversations/{conversation_id}/customer")
def link_conversation_customer(
    conversation_id: str,
    body: WhatsAppConversationCustomerInput,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    """Bind one sender identity to one customer for all future inbound routing."""
    require(tenant, "owner", "admin", "staff")
    conversation = db.scalar(
        select(WhatsAppConversation)
        .where(
            WhatsAppConversation.organization_id == tenant.id,
            WhatsAppConversation.id == conversation_id,
        )
        .with_for_update()
    )
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    customer = db.scalar(
        select(Customer).where(
            Customer.organization_id == tenant.id,
            Customer.id == body.customer_id,
            Customer.active.is_(True),
        )
    )
    if not customer:
        raise HTTPException(404, "Active customer not found")
    contact = db.scalar(
        select(CustomerWhatsAppContact)
        .where(
            CustomerWhatsAppContact.organization_id == tenant.id,
            CustomerWhatsAppContact.phone == conversation.customer_phone,
        )
        .with_for_update()
    )
    if contact and contact.customer_id != customer.id:
        raise HTTPException(
            409,
            "This WhatsApp number is already linked to a different customer",
        )
    if not contact:
        db.add(
            CustomerWhatsAppContact(
                organization_id=tenant.id,
                customer_id=customer.id,
                phone=conversation.customer_phone,
            )
        )
    conversation.customer_id = customer.id
    conversation.customer_name = customer.name
    conversation.customer_match_source = "manual"
    db.commit()
    return {
        "id": conversation.id,
        "customer_id": conversation.customer_id,
        "customer_name": conversation.customer_name,
        "customer_match_source": conversation.customer_match_source,
    }


@router.post("/api/inbox/conversations/{conversation_id}/reply", status_code=201)
def send_reply(
    conversation_id: str,
    body: WhatsAppReplyInput,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    require(tenant, "owner", "admin", "staff")
    conversation = db.scalar(
        select(WhatsAppConversation)
        .where(
            WhatsAppConversation.organization_id == tenant.id,
            WhatsAppConversation.id == conversation_id,
        )
        .with_for_update()
    )
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    existing = db.scalar(
        select(WhatsAppMessage).where(
            WhatsAppMessage.organization_id == tenant.id,
            WhatsAppMessage.client_request_id == body.client_request_id,
        )
    )
    if existing:
        if existing.conversation_id != conversation.id or existing.text != body.text:
            raise HTTPException(409, "Request identifier was already used")
        return {
            "id": existing.id,
            "delivery_status": existing.delivery_status,
            "duplicate": True,
        }

    phone = db.scalar(
        select(WhatsAppPhoneNumber).where(
            WhatsAppPhoneNumber.organization_id == tenant.id,
            WhatsAppPhoneNumber.phone_number_id == conversation.phone_number_id,
            WhatsAppPhoneNumber.active.is_(True),
        )
    )
    linked_token = (
        decrypt_token(phone.access_token_encrypted)
        if phone and phone.access_token_encrypted
        else None
    )
    phone_number_id = (
        conversation.phone_number_id
        if linked_token
        else settings.whatsapp_phone_number_id
    )
    if not linked_token:
        if (
            not has_real_config(settings.whatsapp_access_token.get_secret_value())
            or not phone_number_id
            or not re.fullmatch(r"v\d+\.\d+", settings.whatsapp_graph_api_version)
        ):
            raise HTTPException(503, "WhatsApp Cloud API is not configured")
        if conversation.phone_number_id != phone_number_id:
            raise HTTPException(
                403, "Conversation is not linked to the configured test number"
            )
    if not phone:
        raise HTTPException(
            403, "Configured WhatsApp number is not registered to this workspace"
        )
    try:
        recipient = _normalize_phone(conversation.customer_phone)
    except ValueError as exc:
        raise HTTPException(
            422, "Conversation has an invalid recipient number"
        ) from exc
    if settings.whatsapp_test_mode:
        allowed = set()
        for value in settings.whatsapp_allowed_test_recipients.split(","):
            if value.strip():
                try:
                    allowed.add(_normalize_phone(value))
                except ValueError:
                    continue
        if recipient not in allowed:
            raise HTTPException(
                403, "Recipient is not allow-listed for WhatsApp test mode"
            )
    last_inbound = db.scalar(
        select(WhatsAppMessage.sent_at)
        .where(
            WhatsAppMessage.organization_id == tenant.id,
            WhatsAppMessage.conversation_id == conversation.id,
            WhatsAppMessage.direction == "inbound",
        )
        .order_by(WhatsAppMessage.sent_at.desc(), WhatsAppMessage.id.desc())
        .limit(1)
    )
    if last_inbound is None or as_utc(last_inbound) < as_utc(now()) - MESSAGE_WINDOW:
        raise HTTPException(
            409,
            "The WhatsApp customer-service window is closed; an approved template is required.",
        )
    external_id = (
        _send_meta_text(
            recipient,
            body.text,
            token_override=linked_token,
            phone_override=phone_number_id,
        )
        if linked_token
        else _send_meta_text(recipient, body.text)
    )
    current = now()
    message = WhatsAppMessage(
        organization_id=tenant.id,
        conversation_id=conversation.id,
        phone_number_id=phone_number_id,
        external_id=external_id,
        direction="outbound",
        message_type="text",
        text=body.text,
        customer_phone=conversation.customer_phone,
        customer_name=conversation.customer_name,
        sent_at=current,
        delivery_status="accepted",
        status_updated_at=current,
        client_request_id=body.client_request_id,
    )
    db.add(message)
    conversation.last_message_preview = body.text[:500]
    conversation.last_message_at = current
    db.commit()
    return {
        "id": message.id,
        "delivery_status": message.delivery_status,
        "duplicate": False,
    }


@router.post("/api/inbox/simulator", status_code=201)
def simulate_message(
    body: WhatsAppSimulatorInput,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    require(tenant, "owner", "admin", "staff")
    message = {
        "phone_number_id": body.phone_number_id,
        "id": f"sim_{uuid.uuid4()}",
        "from": body.customer_phone,
        "timestamp": str(int(now().timestamp())),
        "type": "text",
        "text": {"body": body.text},
        "_contact": {"profile": {"name": body.customer_name}},
    }
    phone = db.scalar(
        select(WhatsAppPhoneNumber).where(
            WhatsAppPhoneNumber.organization_id == tenant.id,
            WhatsAppPhoneNumber.phone_number_id == body.phone_number_id,
            WhatsAppPhoneNumber.active.is_(True),
        )
    )
    if not phone:
        raise HTTPException(404, "Register a WhatsApp phone number first")
    try:
        created = _queue_message(db, message)
        event = db.scalar(
            select(WhatsAppWebhookEvent).where(
                WhatsAppWebhookEvent.external_id == message["id"]
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Synthetic message could not be queued") from exc
    processed = (
        _process_event(db, tenant.id, event.id, event.attempts)
        if created and event
        else False
    )
    if db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT set_config('app.organization_id', :tenant, true)"),
            {"tenant": tenant.id},
        )
    stored_message = db.scalar(
        select(WhatsAppMessage).where(
            WhatsAppMessage.organization_id == tenant.id,
            WhatsAppMessage.external_id == message["id"],
        )
    )
    return {
        "status": "processed" if processed else "queued",
        "message_id": message["id"],
        "extraction_draft_id": stored_message.extraction_draft_id,
    }


@router.get("/api/inbox/conversations")
def list_conversations(
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
    view: Literal["active", "unread", "archived", "all"] = Query(default="all"),
    search: str = Query(default="", max_length=120),
    category: Literal[
        "all",
        "business",
        "business_order",
        "business_inquiry",
        "support",
        "personal",
        "spam",
        "needs_review",
    ] = Query(default="all"),
):
    query = select(WhatsAppConversation).where(
        WhatsAppConversation.organization_id == tenant.id
    )
    if view in {"active", "unread"}:
        query = query.where(WhatsAppConversation.archived.is_(False))
    elif view == "archived":
        query = query.where(WhatsAppConversation.archived.is_(True))
    if view == "unread":
        query = query.where(WhatsAppConversation.unread_count > 0)
    preview = WhatsAppConversation.last_message_preview
    if category != "all":
        categories = (
            ["business_order", "business_inquiry", "support"]
            if category == "business"
            else ["needs_review", "unclassified"]
            if category == "needs_review"
            else [category]
        )
        query = query.where(
            select(WhatsAppMessage.id)
            .where(
                WhatsAppMessage.organization_id == tenant.id,
                WhatsAppMessage.conversation_id == WhatsAppConversation.id,
                WhatsAppMessage.direction == "inbound",
                WhatsAppMessage.category.in_(categories),
            )
            .exists()
        )
        preview = (
            select(
                func.coalesce(
                    WhatsAppMessage.text, WhatsAppMessage.message_type + " message"
                )
            )
            .where(
                WhatsAppMessage.organization_id == tenant.id,
                WhatsAppMessage.conversation_id == WhatsAppConversation.id,
                WhatsAppMessage.direction == "inbound",
                WhatsAppMessage.category.in_(categories),
            )
            .order_by(WhatsAppMessage.sent_at.desc(), WhatsAppMessage.id.desc())
            .limit(1)
            .correlate(WhatsAppConversation)
            .scalar_subquery()
        )
    if search.strip():
        needle = f"%{search.strip()}%"
        query = query.where(
            or_(
                WhatsAppConversation.customer_phone.ilike(needle),
                WhatsAppConversation.customer_name.ilike(needle),
                WhatsAppConversation.last_message_preview.ilike(needle),
                select(WhatsAppMessage.id)
                .where(
                    WhatsAppMessage.organization_id == tenant.id,
                    WhatsAppMessage.conversation_id == WhatsAppConversation.id,
                    WhatsAppMessage.text.ilike(needle),
                )
                .exists(),
            )
        )
    return [
        {
            "id": item.id,
            "customer_phone": item.customer_phone,
            "customer_name": item.customer_name,
            "customer_id": item.customer_id,
            "customer_match_source": item.customer_match_source,
            "last_message_preview": (matched_preview or "")[:500],
            "last_message_at": item.last_message_at,
            "unread_count": item.unread_count,
            "archived": item.archived,
            "pinned": item.pinned,
        }
        for item, matched_preview in db.execute(
            query.add_columns(preview)
            .order_by(
                WhatsAppConversation.pinned.desc(),
                WhatsAppConversation.last_message_at.desc(),
                WhatsAppConversation.id,
            )
            .limit(200)
        )
    ]


@router.get("/api/inbox/conversations/{conversation_id}/messages")
def list_messages(
    conversation_id: str,
    mark_read: bool = Query(default=True),
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    conversation = db.scalar(
        select(WhatsAppConversation).where(
            WhatsAppConversation.organization_id == tenant.id,
            WhatsAppConversation.id == conversation_id,
        )
    )
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    if mark_read:
        conversation.unread_count = 0
    messages = db.scalars(
        select(WhatsAppMessage)
        .where(
            WhatsAppMessage.organization_id == tenant.id,
            WhatsAppMessage.conversation_id == conversation_id,
        )
        .order_by(WhatsAppMessage.sent_at, WhatsAppMessage.id)
        .limit(500)
    ).all()
    db.commit()
    return [
        {
            "id": message.id,
            "direction": message.direction,
            "message_type": message.message_type,
            "text": message.text,
            "transcription_status": message.transcription_status,
            "transcription_error": message.transcription_error,
            "sent_at": message.sent_at,
            "extraction_draft_id": message.extraction_draft_id,
            "delivery_status": message.delivery_status,
            "delivery_error_code": message.delivery_error_code,
            "category": message.category,
            "category_reason": message.category_reason,
            "category_reviewed": message.category_reviewed,
            "is_simulated": bool(
                message.external_id and message.external_id.startswith("sim_")
            ),
        }
        for message in messages
    ]


@router.post("/api/inbox/messages/{message_id}/transcription/retry")
def retry_transcription(
    message_id: str,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    require(tenant, "owner", "admin", "staff")
    message = db.scalar(
        select(WhatsAppMessage).where(
            WhatsAppMessage.organization_id == tenant.id,
            WhatsAppMessage.id == message_id,
        )
    )
    if not message:
        raise HTTPException(404, "Message not found")
    if message.message_type not in {"audio", "image"} or message.text:
        raise HTTPException(409, "This message does not need media reading")
    if message.message_type == "image" and not image_ready():
        raise HTTPException(503, "Image extraction is not configured")
    if message.message_type == "audio" and not voice_ready():
        raise HTTPException(503, "Voice transcription is not configured")
    event = db.scalar(
        select(WhatsAppWebhookEvent)
        .where(
            WhatsAppWebhookEvent.organization_id == tenant.id,
            WhatsAppWebhookEvent.message_id == message_id,
        )
        .with_for_update()
    )
    if not event or event.status == "processing":
        raise HTTPException(409, "Media message is already being processed")
    event.status = "queued"
    event.attempts = 0
    event.claimed_at = None
    event.last_error = ""
    event.processed_at = None
    message.transcription_status = "pending"
    message.transcription_error = ""
    message.updated_at = now()
    db.commit()
    return {"status": "queued"}


@router.get("/api/inbox/events")
async def inbox_events(
    request: Request,
    tenant: Tenant = Depends(tenant_context, scope="function"),
    after: str | None = Query(default=None),
):
    try:
        cursor = (
            datetime.fromisoformat(after.replace("Z", "+00:00")) if after else now()
        )
    except ValueError as exc:
        raise HTTPException(422, "Invalid event cursor") from exc

    async def stream():
        current = cursor
        while not await request.is_disconnected():
            with SessionLocal() as db:
                membership = db.execute(
                    text(
                        "SELECT 1 FROM memberships WHERE user_id = :user AND organization_id = :org"
                    ),
                    {"user": tenant.user_id, "org": tenant.id},
                ).first()
                if not membership:
                    yield "event: auth-expired\ndata: {}\n\n"
                    return
                if db.bind.dialect.name == "postgresql":
                    db.execute(
                        text("SELECT set_config('app.organization_id', :tenant, true)"),
                        {"tenant": tenant.id},
                    )
                messages = db.scalars(
                    select(WhatsAppMessage)
                    .where(
                        WhatsAppMessage.organization_id == tenant.id,
                        WhatsAppMessage.updated_at > current,
                    )
                    .order_by(WhatsAppMessage.updated_at, WhatsAppMessage.id)
                    .limit(100)
                ).all()
                if messages:
                    current = as_utc(messages[-1].updated_at)
                    payload = [
                        {
                            "id": item.id,
                            "conversation_id": item.conversation_id,
                            "updated_at": as_utc(item.updated_at).isoformat(),
                        }
                        for item in messages
                    ]
                    yield f"event: messages\ndata: {json.dumps(payload)}\n\n"
                else:
                    yield ": keep-alive\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class ConversationManagement(StrictModel):
    archived: bool | None = None
    pinned: bool | None = None
    read_state: Literal["read", "unread"] | None = None


@router.patch("/api/inbox/conversations/{conversation_id}/management")
def manage_conversation(
    conversation_id: str,
    body: ConversationManagement,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    require(tenant, "owner", "admin", "staff")
    conversation = db.scalar(
        select(WhatsAppConversation)
        .where(
            WhatsAppConversation.organization_id == tenant.id,
            WhatsAppConversation.id == conversation_id,
        )
        .with_for_update()
    )
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    if body.archived is None and body.pinned is None and body.read_state is None:
        raise HTTPException(422, "Choose a conversation action")
    if body.archived is not None:
        conversation.archived = body.archived
    if body.pinned is not None:
        conversation.pinned = body.pinned
    if body.read_state is not None:
        conversation.unread_count = (
            0 if body.read_state == "read" else max(1, conversation.unread_count)
        )
    db.commit()
    return {
        "id": conversation.id,
        "archived": conversation.archived,
        "pinned": conversation.pinned,
        "unread_count": conversation.unread_count,
    }
