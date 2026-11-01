import hashlib
import io
import json

import httpx
import pytest
from PIL import Image, PngImagePlugin
from pydantic import SecretStr
from sqlalchemy import select

from app import image_extraction as images
from app import main, voice, whatsapp
from app.config import settings
from app.extraction import LocalExtractor
from app.models import ExtractionDraft, WhatsAppMessage, WhatsAppWebhookEvent

from .conftest import catalog, order_body, register
from .test_whatsapp import connect_phone, payload, signed_post


def image_bytes():
    output = io.BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("Private metadata", "must-not-leave-server")
    Image.new("RGB", (160, 100), "white").save(output, format="PNG", pnginfo=metadata)
    return output.getvalue()


def configure(monkeypatch, text="Rice 2", uncertain=False, status=200):
    requests = []
    monkeypatch.setattr(settings, "ai_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", SecretStr("test-image-key"))
    monkeypatch.setattr(settings, "openai_model", "test-model")
    monkeypatch.setattr(settings, "openai_vision_model", "")
    monkeypatch.setattr(settings, "image_extraction_enabled", True)
    monkeypatch.setattr(main, "get_extractor", lambda: LocalExtractor())
    monkeypatch.setattr(whatsapp, "get_extractor", lambda: LocalExtractor())

    def handler(request):
        requests.append(request)
        body = json.loads(request.content)
        assert request.headers["Authorization"] == "Bearer test-image-key"
        assert body["store"] is False
        assert body["text"]["format"]["strict"]
        assert body["input"][0]["content"][1]["image_url"].startswith(
            "data:image/png;base64,"
        )
        assert "catalog" not in body
        if status != 200:
            return httpx.Response(
                status,
                json={
                    "error": {
                        "code": "credit_balance_exhausted",
                        "type": "insufficient_quota",
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {"text": text, "uncertain": uncertain}
                                ),
                            }
                        ]
                    }
                ],
            },
        )

    monkeypatch.setattr(
        images,
        "image_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )
    return requests


def upload(client, raw=None, mime="image/png"):
    return client.post(
        "/api/extractions/image",
        content=raw if raw is not None else image_bytes(),
        headers={"Content-Type": mime},
    )


@pytest.mark.parametrize("text", ["Rice 2", "සහල් 2", "அரிசி 2"])
def test_image_upload_creates_only_a_reviewable_tenant_draft(setup, monkeypatch, text):
    client, factory = setup
    register(client)
    customer, product = catalog(client)
    client.put(
        f"/api/products/{product['id']}",
        json={
            "name": "Rice",
            "sku": "RICE-1",
            "price_minor": 25000,
            "aliases": ["සහල්", "அரிசி"],
        },
    )
    requests = configure(monkeypatch, text, uncertain=True)
    response = upload(client)
    assert response.status_code == 201, response.text
    draft = response.json()
    assert draft["source_text"] == text
    assert draft["result"]["source_type"] == "image_text"
    assert "image_text_uncertain" in draft["result"]["flags"]
    assert draft["result"]["requires_confirmation"]
    assert draft["result"]["items"][0]["quantity"] == 2
    assert client.get("/api/orders").json() == []
    assert client.get("/api/products").json()[0]["stock"] == 30
    with factory() as db:
        assert len(db.scalars(select(ExtractionDraft)).all()) == 1
    assert len(requests) == 1
    register(client, "other")
    assert client.get(f"/api/extractions/{draft['id']}").status_code == 404


def test_image_prices_do_not_replace_catalog_prices(setup, monkeypatch):
    client, _ = setup
    register(client)
    customer, product = catalog(client)
    configure(monkeypatch, "Rice 2; price LKR 1")
    draft = upload(client).json()
    body = {
        **order_body(customer, product),
        "draft_id": draft["id"],
        "flags_acknowledged": True,
    }
    created = client.post(
        "/api/orders",
        json=body,
        headers={"Idempotency-Key": "image-order-confirmation"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["total_minor"] == 50000


def test_invalid_empty_or_oversized_images_never_reach_the_provider(setup, monkeypatch):
    client, _ = setup
    register(client)
    requests = configure(monkeypatch)
    assert upload(client, b"<svg onload='evil'>", "image/svg+xml").status_code == 415
    assert upload(client, b"not-an-image").status_code == 422
    assert upload(client, b"").status_code == 422
    assert upload(client, b"0" * (images.MAX_IMAGE_BYTES + 1)).status_code == 413
    assert requests == []


def test_normalization_strips_metadata_and_rejects_huge_dimensions(monkeypatch):
    normalized, mime = images.normalize_image(image_bytes())
    assert mime == "image/png"
    assert b"must-not-leave-server" not in normalized
    monkeypatch.setattr(images, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(images.ImageError, match="dimensions"):
        images.normalize_image(image_bytes())


def test_no_readable_text_creates_no_draft_and_quota_errors_are_actionable(
    setup, monkeypatch
):
    client, _ = setup
    register(client)
    configure(monkeypatch, "")
    assert upload(client).status_code == 422
    configure(monkeypatch, status=429)
    response = upload(client)
    assert response.status_code == 503
    assert "credits" in response.json()["detail"]


def test_disabled_image_processing_makes_no_provider_call(setup, monkeypatch):
    client, _ = setup
    register(client)
    requests = configure(monkeypatch)
    monkeypatch.setattr(settings, "image_extraction_enabled", False)
    assert upload(client).status_code == 503
    assert requests == []


def test_whatsapp_image_reading_uses_own_media_and_does_not_duplicate_work(
    setup, monkeypatch
):
    client, factory = setup
    register(client)
    catalog(client)
    connect_phone(client)
    monkeypatch.setattr(settings, "meta_app_secret", SecretStr("test-meta-secret"))
    monkeypatch.setattr(
        settings, "whatsapp_access_token", SecretStr("test-media-token")
    )
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "123456789012345")
    monkeypatch.setattr(settings, "whatsapp_graph_api_version", "v26.0")
    requests = configure(monkeypatch, "Rice 2")
    raw = image_bytes()
    media_requests = []

    def media_handler(request):
        media_requests.append(request)
        assert request.headers["Authorization"] == "Bearer test-media-token"
        if request.url.host == "graph.facebook.com":
            return httpx.Response(
                200,
                json={
                    "id": "12345",
                    "url": "https://lookaside.fbsbx.com/image",
                    "file_size": len(raw),
                    "mime_type": "image/png",
                    "sha256": hashlib.sha256(raw).hexdigest(),
                },
            )
        return httpx.Response(200, content=raw)

    monkeypatch.setattr(
        voice,
        "media_client",
        lambda: httpx.Client(transport=httpx.MockTransport(media_handler)),
    )
    data = payload()
    incoming = data["entry"][0]["changes"][0]["value"]["messages"][0]
    incoming.pop("text")
    incoming.update(
        type="image",
        image={
            "id": "12345",
            "mime_type": "image/png",
            "caption": "Please deliver tomorrow",
        },
    )
    assert signed_post(client, data).json()["queued"] == 1
    assert signed_post(client, data).json()["queued"] == 0
    with factory() as db:
        event = db.scalar(select(WhatsAppWebhookEvent))
        assert whatsapp._process_event(db, event.organization_id, event.id, 0)
        message = db.scalar(select(WhatsAppMessage))
        assert message.transcription_status == "transcribed"
        assert message.media_caption == "Please deliver tomorrow"
        assert message.text == "Please deliver tomorrow\nRice 2"
        draft = db.scalar(select(ExtractionDraft))
        assert "image_text_requires_review" in draft.result["flags"]
    assert len(requests) == 1
    assert len(media_requests) == 2
    assert client.get("/api/orders").json() == []


def test_jpeg_exif_is_removed_before_external_processing():
    output = io.BytesIO()
    photo = Image.new("RGB", (160, 100), "white")
    exif = Image.Exif()
    exif[315] = "PrivatePhotoAuthor"
    photo.save(output, format="JPEG", exif=exif)
    normalized, _ = images.normalize_image(output.getvalue())
    assert b"PrivatePhotoAuthor" not in normalized
    with Image.open(io.BytesIO(normalized)) as cleaned:
        assert not cleaned.getexif()


def test_viewer_cannot_trigger_paid_image_processing(setup, monkeypatch):
    from app.models import Membership

    client, factory = setup
    account = register(client)
    requests = configure(monkeypatch)
    with factory() as db:
        membership = db.scalar(
            select(Membership).where(
                Membership.organization_id == account["organization_id"]
            )
        )
        membership.role = "viewer"
        db.commit()
    assert upload(client).status_code == 403
    assert requests == []
