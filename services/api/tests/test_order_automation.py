from datetime import timedelta

import pytest
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import func, select

from app import automation, whatsapp
from app.config import settings
from app.models import (
    ExtractionDraft,
    Membership,
    Order,
    Product,
    StockMovement,
    WhatsAppBotReply,
    WhatsAppMessage,
    now,
)

from .conftest import catalog, order_body, register
from .test_whatsapp import connect_phone, payload, signed_post


def setup_bot(setup, monkeypatch):
    client, factory = setup
    account = register(client)
    customer, product = catalog(client)
    connect_phone(client)
    monkeypatch.setattr(settings, "meta_app_secret", SecretStr("test-meta-secret"))
    monkeypatch.setattr(
        settings, "whatsapp_access_token", SecretStr("test-whatsapp-token")
    )
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "123456789012345")
    monkeypatch.setattr(settings, "whatsapp_graph_api_version", "v26.0")
    monkeypatch.setattr(settings, "whatsapp_allowed_test_recipients", "+94770001122")
    monkeypatch.setattr(settings, "whatsapp_test_mode", True)
    monkeypatch.setattr(whatsapp, "SessionLocal", factory)
    monkeypatch.setattr(automation, "SessionLocal", factory)
    assert client.get("/api/inbox/chatbot-settings").json()["enabled"] is False
    assert (
        client.put(
            "/api/inbox/chatbot-settings",
            json={"enabled": True, "answer_business_questions": True},
        ).status_code
        == 200
    )
    return client, factory, account, customer, product


def incoming(client, body="Rice 2", message_id="wamid.bot.1"):
    data = payload(external_id=message_id)
    msg = data["entry"][0]["changes"][0]["value"]["messages"][0]
    msg["timestamp"] = str(int(now().timestamp()))
    msg["text"]["body"] = body
    result = signed_post(client, data)
    assert result.status_code == 200, result.text
    whatsapp.process_pending_once()
    return data


def test_whatsapp_order_availability_owner_approval_stock_and_confirmation(
    setup, monkeypatch
):
    client, factory, account, customer, product = setup_bot(setup, monkeypatch)
    sent = []

    def send(recipient, body, **kwargs):
        sent.append((recipient, body))
        return f"wamid.bot.out.{len(sent)}"

    monkeypatch.setattr(whatsapp, "_send_meta_text", send)
    data = incoming(client)
    pending = client.get("/api/inbox/order-requests").json()
    assert len(pending) == 1 and pending[0]["availability"][0]["status"] == "available"
    assert client.get("/api/analytics").json()["pending_approvals"] == 1
    draft_id = pending[0]["draft"]["id"]
    with factory() as db:
        assert db.get(Product, product["id"]).stock == 30
        assert db.scalar(select(func.count()).select_from(Order)) == 0
    assert automation.process_bot_replies_once() == 1
    assert "not a confirmed order" in sent[0][1] and "currently available" in sent[0][1]
    assert signed_post(client, data).json()["queued"] == 0
    assert automation.process_bot_replies_once() == 0 and len(sent) == 1
    body = {
        **order_body(customer, product),
        "draft_id": draft_id,
        "flags_acknowledged": True,
    }
    with factory() as db:
        member = db.get(Membership, (account["id"], account["organization_id"]))
        member.role = "staff"
        db.commit()
    assert (
        client.post(
            "/api/orders", json=body, headers={"Idempotency-Key": "bot-owner-approval"}
        ).status_code
        == 403
    )
    with factory() as db:
        db.get(Membership, (account["id"], account["organization_id"])).role = "owner"
        db.commit()
    approved = client.post(
        "/api/orders", json=body, headers={"Idempotency-Key": "bot-owner-approval"}
    )
    assert approved.status_code == 201, approved.text
    assert (
        client.post(
            "/api/orders", json=body, headers={"Idempotency-Key": "bot-owner-approval"}
        ).status_code
        == 201
    )
    assert client.get("/api/inbox/order-requests").json() == []
    assert client.get("/api/analytics").json()["pending_approvals"] == 0
    with factory() as db:
        assert db.get(Product, product["id"]).stock == 28
        assert db.scalar(select(func.count()).select_from(Order)) == 1
        assert (
            len(
                list(db.scalars(select(StockMovement).where(StockMovement.delta == -2)))
            )
            == 1
        )
    assert automation.process_bot_replies_once() == 1
    assert "approved your order" in sent[-1][1]
    assert automation.process_bot_replies_once() == 0 and len(sent) == 2


def test_stock_changes_unknown_units_rejection_and_no_premature_confirmation(
    setup, monkeypatch
):
    client, factory, _, customer, product = setup_bot(setup, monkeypatch)
    incoming(client, "Rice 40")
    pending = client.get("/api/inbox/order-requests").json()[0]
    assert pending["availability"][0]["status"] == "insufficient_stock"
    body = {
        **order_body(customer, product, 40),
        "draft_id": pending["draft"]["id"],
        "flags_acknowledged": True,
    }
    assert (
        client.post(
            "/api/orders",
            json=body,
            headers={"Idempotency-Key": "out-of-stock-approval"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/inbox/order-requests/{pending['draft']['id']}/reject"
        ).status_code
        == 200
    )
    assert client.get("/api/inbox/order-requests").json() == []
    assert (
        client.post(
            "/api/orders",
            json={
                **body,
                "items": [{"product_id": product["id"], "quantity": 2}],
                "expected_total_minor": 50000,
            },
            headers={"Idempotency-Key": "rejected-order-approval"},
        ).status_code
        == 409
    )
    with factory() as db:
        assert db.get(Product, product["id"]).stock == 30
        assert db.scalar(select(func.count()).select_from(Order)) == 0
        assert (
            db.scalar(
                select(func.count())
                .select_from(WhatsAppBotReply)
                .where(WhatsAppBotReply.kind == "confirmed")
            )
            == 0
        )
        result = {
            "items": [
                {
                    "product_id": product["id"],
                    "quantity": 2,
                    "unit": "cartons",
                    "flags": [],
                }
            ]
        }
        assert (
            automation.availability(db, product["organization_id"], result)[0]["status"]
            == "needs_review"
        )


def test_blocked_replies_are_retryable_but_unknown_delivery_is_not_resent(
    setup, monkeypatch
):
    client, factory, _, _, _ = setup_bot(setup, monkeypatch)
    incoming(client)
    monkeypatch.setattr(settings, "whatsapp_allowed_test_recipients", "")
    sends = []

    def timeout(*args, **kwargs):
        sends.append(True)
        raise HTTPException(504, "Delivery unknown")

    monkeypatch.setattr(whatsapp, "_send_meta_text", timeout)
    assert automation.process_bot_replies_once() == 0
    jobs = client.get("/api/inbox/chatbot-replies").json()
    assert jobs[0]["status"] == "blocked" and sends == []
    monkeypatch.setattr(settings, "whatsapp_allowed_test_recipients", "+94770001122")
    assert (
        client.post(f"/api/inbox/chatbot-replies/{jobs[0]['id']}/retry").status_code
        == 200
    )
    assert automation.process_bot_replies_once() == 0
    assert client.get("/api/inbox/chatbot-replies").json()[0]["status"] == "unknown"
    assert automation.process_bot_replies_once() == 0 and len(sends) == 1
    assert (
        client.post(f"/api/inbox/chatbot-replies/{jobs[0]['id']}/retry").status_code
        == 409
    )


def test_bot_settings_private_spam_simulator_and_tenant_isolation(setup, monkeypatch):
    client, factory, account, _, _ = setup_bot(setup, monkeypatch)
    for index, body in enumerate(["Happy birthday", "Send your OTP to claim a prize"]):
        incoming(client, body, f"wamid.excluded.{index}")
    simulated = client.post(
        "/api/inbox/simulator",
        json={
            "phone_number_id": "123456789012345",
            "customer_phone": "+94770001122",
            "text": "Rice 2",
        },
    )
    assert simulated.status_code == 201
    assert client.get("/api/inbox/chatbot-replies").json() == []
    assert (
        client.put(
            "/api/inbox/chatbot-settings",
            json={"enabled": True, "owner_approval_required": False},
        ).status_code
        == 422
    )
    register(client, "other-bot")
    assert client.get("/api/inbox/order-requests").json() == []
    assert client.get("/api/inbox/chatbot-replies").json() == []
    assert client.get("/api/inbox/chatbot-settings").json()["enabled"] is False
    assert (
        client.get(
            "/api/inbox/chatbot-settings",
            headers={"X-Organization-ID": account["organization_id"]},
        ).status_code
        == 403
    )


def test_bot_off_and_stale_inflight_jobs_do_not_send(setup, monkeypatch):
    client, factory, _, _, _ = setup_bot(setup, monkeypatch)
    incoming(client)
    with factory() as db:
        job = db.scalar(select(WhatsAppBotReply))
        job.status = "sending"
        job.updated_at = now() - timedelta(minutes=6)
        db.commit()
    assert automation.process_bot_replies_once() == 0
    assert client.get("/api/inbox/chatbot-replies").json()[0]["status"] == "unknown"
    incoming(client, "Rice 3", "wamid.bot.off")
    assert (
        client.put(
            "/api/inbox/chatbot-settings",
            json={"enabled": False, "answer_business_questions": True},
        ).status_code
        == 200
    )
    assert automation.process_bot_replies_once() == 0
    assert any(
        job["status"] == "cancelled"
        for job in client.get("/api/inbox/chatbot-replies").json()
    )


def test_bot_rechecks_stock_and_answers_saved_business_questions(setup, monkeypatch):
    client, factory, account, _, product = setup_bot(setup, monkeypatch)
    sent = []

    def send(recipient, body, **kwargs):
        sent.append(body)
        return f"wamid.checked.{len(sent)}"

    monkeypatch.setattr(whatsapp, "_send_meta_text", send)
    incoming(client)
    assert (
        client.post(
            f"/api/products/{product['id']}/stock",
            json={"delta": -29, "reason": "Another confirmed sale"},
        ).status_code
        == 200
    )
    assert automation.process_bot_replies_once() == 1
    assert "requested quantity is not currently available" in sent[0]
    from app.models import Organization

    with factory() as db:
        org = db.get(Organization, account["organization_id"])
        org.business_profile = {
            **org.business_profile,
            "hours": "Monday to Friday, 9am to 5pm",
        }
        db.commit()
    incoming(client, "What are your opening hours?", "wamid.faq.hours")
    assert automation.process_bot_replies_once() == 1
    assert "Monday to Friday, 9am to 5pm" in sent[-1]
    assert "order-specific terms" in sent[-1]


def test_availability_reply_languages_and_combined_quantities(setup):
    client, factory = setup
    account = register(client)
    _, product = catalog(client)
    result = {
        "items": [
            {"product_id": product["id"], "quantity": 20, "unit": "units", "flags": []},
            {"product_id": product["id"], "quantity": 20, "unit": "units", "flags": []},
        ]
    }
    with factory() as db:
        rows = automation.availability(db, account["organization_id"], result)
        assert all(row["status"] == "insufficient_stock" for row in rows)
    assert "ඉල්ලීම" in automation.availability_reply(rows, "හාල් 20")
    assert "கோரிக்கை" in automation.availability_reply(rows, "அரிசி 20")
    assert "not a confirmed order" in automation.availability_reply(rows, "Rice 20")


@pytest.mark.parametrize("business_type", ["wholesale", "software"])
def test_enabled_local_chatbot_never_calls_external_text_ai(
    setup, monkeypatch, business_type
):
    from app import service_requests
    from app.models import Organization

    client, factory, account, _, _ = setup_bot(setup, monkeypatch)
    monkeypatch.setattr(settings, "ai_provider", "openai")

    def forbidden(*args, **kwargs):
        raise AssertionError("Local chatbot must not call an external AI")

    monkeypatch.setattr(whatsapp, "get_extractor", forbidden)
    monkeypatch.setattr(service_requests, "model_fields", forbidden)
    with factory() as db:
        db.get(Organization, account["organization_id"]).business_type = business_type
        db.commit()
    incoming(client)
    with factory() as db:
        draft = db.scalar(select(ExtractionDraft))
        assert draft is not None and draft.result["provider"] == "local-rules-v1"
    assert (
        client.get("/api/inbox/chatbot-settings").json()["processing_mode"] == "local"
    )


def test_local_chatbot_media_is_kept_for_manual_review_without_download(
    setup, monkeypatch
):
    client, factory, _, _, _ = setup_bot(setup, monkeypatch)

    def forbidden(*args, **kwargs):
        raise AssertionError("Local chatbot must not download media or call AI")

    monkeypatch.setattr(whatsapp, "download_audio", forbidden)
    monkeypatch.setattr(whatsapp, "transcribe_audio", forbidden)
    data = payload(external_id="wamid.local.audio")
    message = data["entry"][0]["changes"][0]["value"]["messages"][0]
    message.pop("text")
    message.update(type="audio", audio={"id": "12345", "mime_type": "audio/wav"})
    assert signed_post(client, data).status_code == 200
    assert whatsapp.process_pending_once() == 1
    with factory() as db:
        stored = db.scalar(select(WhatsAppMessage))
        assert (
            stored.transcription_status == "failed"
            and stored.extraction_draft_id is None
        )
        assert "Local chatbot mode" in stored.transcription_error
