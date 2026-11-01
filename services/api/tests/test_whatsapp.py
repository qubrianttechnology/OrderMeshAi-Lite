import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import httpx
from pydantic import SecretStr
from sqlalchemy import select

from app import whatsapp
from app.ai_provider import ProviderUnavailable
from app.config import settings
from app.models import (
    CustomerWhatsAppContact,
    ExtractionDraft,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppPhoneNumber,
    WhatsAppWebhookEvent,
    as_utc,
)

from .conftest import catalog, register


def connect_phone(client, phone_number_id="123456789012345"):
    response = client.post(
        "/api/inbox/phone-numbers",
        json={
            "phone_number_id": phone_number_id,
            "display_phone_number": "+94722616616",
            "business_account_id": "987654321",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def payload(phone_number_id="123456789012345", external_id="wamid.test.1"):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": phone_number_id},
                            "contacts": [
                                {
                                    "wa_id": "94770001122",
                                    "profile": {"name": "Nimal"},
                                }
                            ],
                            "messages": [
                                {
                                    "from": "94770001122",
                                    "id": external_id,
                                    "timestamp": "1735689600",
                                    "type": "text",
                                    "text": {"body": "Rice 2"},
                                }
                            ],
                        }
                    }
                ]
            }
        ],
    }


def signed_post(client, data, secret="test-meta-secret"):
    raw = json.dumps(data, separators=(",", ":")).encode()
    signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return client.post(
        "/webhooks/whatsapp",
        content=raw,
        headers={"X-Hub-Signature-256": f"sha256={signature}"},
    )


def create_replyable_conversation(client, phone_number_id):
    response = client.post(
        "/api/inbox/simulator",
        json={
            "phone_number_id": phone_number_id,
            "customer_phone": "+94770001122",
            "customer_name": "Nimal",
            "text": "Hello",
        },
    )
    assert response.status_code == 201, response.text
    conversations = client.get("/api/inbox/conversations").json()
    return conversations[0]


def configure_meta_sender(monkeypatch, handler):
    monkeypatch.setattr(settings, "whatsapp_access_token", SecretStr("test-only-token"))
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "123456789012345")
    monkeypatch.setattr(settings, "whatsapp_graph_api_version", "v99.0")
    monkeypatch.setattr(settings, "whatsapp_test_mode", True)
    monkeypatch.setattr(settings, "whatsapp_allowed_test_recipients", "+94 77 000 1122")
    monkeypatch.setattr(
        whatsapp,
        "_meta_client",
        lambda: httpx.Client(
            transport=httpx.MockTransport(handler),
            timeout=httpx.Timeout(15, connect=5),
        ),
    )


def test_webhook_signature_verification_and_deduplication(setup, monkeypatch):
    client, factory = setup
    register(client)
    connect_phone(client)
    monkeypatch.setattr(settings, "meta_app_secret", SecretStr("test-meta-secret"))

    data = payload()
    raw = json.dumps(data, separators=(",", ":")).encode()
    denied = client.post(
        "/webhooks/whatsapp",
        content=raw,
        headers={"X-Hub-Signature-256": "sha256=" + "0" * 64},
    )
    assert denied.status_code == 403

    accepted = signed_post(client, data)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json() == {"status": "accepted", "queued": 1}
    assert signed_post(client, data).json()["queued"] == 0

    with factory() as db:
        assert len(db.scalars(select(WhatsAppMessage)).all()) == 1
        assert len(db.scalars(select(WhatsAppWebhookEvent)).all()) == 1
        conversation = db.scalar(select(WhatsAppConversation))
        assert conversation.customer_name == "Nimal"
        assert conversation.unread_count == 1


def test_inbound_message_uses_exact_customer_phone_not_meta_profile_name(
    setup, monkeypatch
):
    client, factory = setup
    account = register(client)
    customer = client.post(
        "/api/customers",
        json={"name": "Perera Stores", "phone": "+94 77 000 1122"},
    ).json()
    connect_phone(client)
    monkeypatch.setattr(settings, "meta_app_secret", SecretStr("test-meta-secret"))

    data = payload()
    data["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"] = (
        "An untrusted profile name"
    )
    response = signed_post(client, data)
    assert response.status_code == 200, response.text

    conversations = client.get("/api/inbox/conversations").json()
    assert conversations == [
        {
            **conversations[0],
            "customer_id": customer["id"],
            "customer_name": "Perera Stores",
            "customer_match_source": "customer_phone",
        }
    ]
    with factory() as db:
        stored = db.scalar(select(WhatsAppConversation))
        assert stored.organization_id == account["organization_id"]
        assert stored.customer_phone == "94770001122"


def test_staff_can_link_unassigned_sender_and_future_messages_reuse_identity(setup):
    client, factory = setup
    account = register(client)
    customer = client.post("/api/customers", json={"name": "Lakmini Traders"}).json()
    phone = connect_phone(client)
    simulated = client.post(
        "/api/inbox/simulator",
        json={
            "phone_number_id": phone["phone_number_id"],
            "customer_phone": "+94770001122",
            "customer_name": "Nimal profile",
            "text": "Rice 2",
        },
    )
    assert simulated.status_code == 201, simulated.text
    conversation = client.get("/api/inbox/conversations").json()[0]
    assert conversation["customer_id"] is None
    linked = client.put(
        f"/api/inbox/conversations/{conversation['id']}/customer",
        json={"customer_id": customer["id"]},
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["customer_match_source"] == "manual"
    with factory() as db:
        contact = db.scalar(select(CustomerWhatsAppContact))
        assert contact.organization_id == account["organization_id"]
        assert contact.customer_id == customer["id"]
        assert contact.phone == "94770001122"

    second = client.post(
        "/api/inbox/simulator",
        json={
            "phone_number_id": phone["phone_number_id"],
            "customer_phone": "94770001122",
            "customer_name": "Different profile name",
            "text": "Rice 1",
        },
    )
    assert second.status_code == 201, second.text
    updated = client.get("/api/inbox/conversations").json()[0]
    assert updated["customer_id"] == customer["id"]
    assert updated["customer_name"] == "Lakmini Traders"
    assert updated["customer_match_source"] == "whatsapp_contact"


def test_reply_uses_mocked_meta_client_and_is_idempotent(setup, monkeypatch):
    client, factory = setup
    register(client)
    phone = connect_phone(client)
    conversation = create_replyable_conversation(client, phone["phone_number_id"])
    requests = []

    def mocked_meta(request):
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer test-only-token"
        assert request.url.path.endswith("/123456789012345/messages")
        assert json.loads(request.read())["to"] == "94770001122"
        return httpx.Response(200, json={"messages": [{"id": "wamid.outbound.1"}]})

    configure_meta_sender(monkeypatch, mocked_meta)
    body = {
        "text": "We received your message.",
        "client_request_id": "request-id-0000001",
    }
    path = f"/api/inbox/conversations/{conversation['id']}/reply"
    first = client.post(path, json=body)
    second = client.post(path, json=body)

    assert first.status_code == 201, first.text
    assert first.json()["delivery_status"] == "accepted"
    assert second.status_code == 201, second.text
    assert second.json()["duplicate"] is True
    assert len(requests) == 1
    with factory() as db:
        outbound = db.scalar(
            select(WhatsAppMessage).where(WhatsAppMessage.direction == "outbound")
        )
        assert outbound.external_id == "wamid.outbound.1"
        assert outbound.client_request_id == body["client_request_id"]


def test_reply_enforces_allowlist_and_customer_service_window(setup, monkeypatch):
    client, factory = setup
    register(client)
    phone = connect_phone(client)
    conversation = create_replyable_conversation(client, phone["phone_number_id"])
    called = False

    def mocked_meta(_request):
        nonlocal called
        called = True
        return httpx.Response(200, json={"messages": [{"id": "wamid.outbound.2"}]})

    configure_meta_sender(monkeypatch, mocked_meta)
    monkeypatch.setattr(settings, "whatsapp_allowed_test_recipients", "+14155550123")
    path = f"/api/inbox/conversations/{conversation['id']}/reply"
    body = {"text": "Hello", "client_request_id": "request-id-0000002"}
    assert client.post(path, json=body).status_code == 403
    assert not called

    monkeypatch.setattr(settings, "whatsapp_allowed_test_recipients", "+94770001122")
    with factory() as db:
        inbound = db.scalar(
            select(WhatsAppMessage).where(WhatsAppMessage.direction == "inbound")
        )
        inbound.sent_at = datetime.now(timezone.utc) - timedelta(hours=25)
        db.commit()
    assert client.post(path, json=body).status_code == 409
    assert not called


def test_reply_handles_meta_timeout_and_requires_authentication(setup, monkeypatch):
    client, _factory = setup
    register(client)
    phone = connect_phone(client)
    conversation = create_replyable_conversation(client, phone["phone_number_id"])

    def timeout(_request):
        raise httpx.ConnectTimeout("mock timeout")

    configure_meta_sender(monkeypatch, timeout)
    path = f"/api/inbox/conversations/{conversation['id']}/reply"
    body = {"text": "Hello", "client_request_id": "request-id-0000003"}
    assert client.post(path, json=body).status_code == 504
    client.cookies.clear()
    assert client.post(path, json=body).status_code == 401
    register(client, "reply-other")
    assert client.post(path, json=body).status_code == 404


def test_reply_safely_handles_meta_errors_and_invalid_configuration(setup, monkeypatch):
    client, _factory = setup
    register(client)
    phone = connect_phone(client)
    conversation = create_replyable_conversation(client, phone["phone_number_id"])
    response_queue = [
        httpx.Response(429, json={"error": {"message": "private provider detail"}}),
        httpx.Response(401, json={"error": {"message": "private provider detail"}}),
        httpx.Response(200, json={"messages": []}),
    ]

    def mocked_meta(_request):
        return response_queue.pop(0)

    configure_meta_sender(monkeypatch, mocked_meta)
    path = f"/api/inbox/conversations/{conversation['id']}/reply"
    for index, expected in enumerate((429, 502, 502), start=5):
        response = client.post(
            path,
            json={
                "text": "Hello",
                "client_request_id": f"request-id-000000{index}",
            },
        )
        assert response.status_code == expected
        assert "private provider detail" not in response.text

    monkeypatch.setattr(settings, "whatsapp_access_token", SecretStr(""))
    missing_credential_requests = []
    monkeypatch.setattr(
        whatsapp,
        "_meta_client",
        lambda: httpx.Client(
            transport=httpx.MockTransport(
                lambda request: (
                    missing_credential_requests.append(request)
                    or httpx.Response(200, json={"messages": [{"id": "unexpected"}]})
                )
            ),
            timeout=httpx.Timeout(15, connect=5),
        ),
    )
    response = client.post(
        path,
        json={"text": "Hello", "client_request_id": "request-id-0000010"},
    )
    assert response.status_code == 503
    assert not missing_credential_requests
    monkeypatch.setattr(settings, "whatsapp_access_token", SecretStr("test-only-token"))
    monkeypatch.setattr(settings, "whatsapp_graph_api_version", "invalid")
    response = client.post(
        path,
        json={"text": "Hello", "client_request_id": "request-id-0000011"},
    )
    assert response.status_code == 503


def test_delivery_status_updates_are_monotonic_and_persisted(setup, monkeypatch):
    client, factory = setup
    register(client)
    phone = connect_phone(client)
    conversation = create_replyable_conversation(client, phone["phone_number_id"])

    def mocked_meta(_request):
        return httpx.Response(200, json={"messages": [{"id": "wamid.outbound.3"}]})

    configure_meta_sender(monkeypatch, mocked_meta)
    response = client.post(
        f"/api/inbox/conversations/{conversation['id']}/reply",
        json={"text": "Thanks", "client_request_id": "request-id-0000004"},
    )
    assert response.status_code == 201, response.text
    monkeypatch.setattr(settings, "meta_app_secret", SecretStr("test-meta-secret"))
    event_time = int(datetime.now(timezone.utc).timestamp()) + 10

    def status_event(status, timestamp):
        return {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {
                                    "phone_number_id": phone["phone_number_id"]
                                },
                                "statuses": [
                                    {
                                        "id": "wamid.outbound.3",
                                        "status": status,
                                        "timestamp": str(timestamp),
                                    }
                                ],
                            }
                        }
                    ]
                }
            ],
        }

    assert signed_post(client, status_event("read", event_time + 1)).status_code == 200
    assert signed_post(client, status_event("delivered", event_time)).status_code == 200
    with factory() as db:
        outbound = db.scalar(
            select(WhatsAppMessage).where(
                WhatsAppMessage.external_id == "wamid.outbound.3"
            )
        )
        assert outbound.delivery_status == "read"


def test_queue_retry_claim_uses_exponential_backoff(setup, monkeypatch):
    client, factory = setup
    register(client)
    catalog(client)
    connect_phone(client)
    monkeypatch.setattr(settings, "meta_app_secret", SecretStr("test-meta-secret"))
    current = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(whatsapp, "now", lambda: current)
    monkeypatch.setattr(whatsapp, "SessionLocal", factory)

    real_get_extractor = whatsapp.get_extractor

    class FailingExtractor:
        def extract(self, *_args):
            raise ProviderUnavailable("temporary provider failure")

    monkeypatch.setattr(whatsapp, "get_extractor", lambda: FailingExtractor())
    response = signed_post(client, payload())
    assert response.status_code == 200, response.text
    with factory() as db:
        event = db.scalar(select(WhatsAppWebhookEvent))
        event_id = event.id

    assert whatsapp.process_pending_once() == 0
    with factory() as db:
        event = db.get(WhatsAppWebhookEvent, event_id)
        assert event.status == "queued"
        assert event.attempts == 1
        assert as_utc(event.claimed_at) == current

    assert whatsapp.process_pending_once() == 0
    monkeypatch.setattr(whatsapp, "get_extractor", real_get_extractor)
    with factory() as db:
        event = db.get(WhatsAppWebhookEvent, event_id)
        event.claimed_at = current - timedelta(seconds=3)
        db.commit()

    assert whatsapp.process_pending_once() == 1
    with factory() as db:
        event = db.get(WhatsAppWebhookEvent, event_id)
        assert event.status == "processed"
        assert event.attempts == 2
        message = db.scalar(select(WhatsAppMessage))
        assert message.extraction_draft_id is not None


def test_inbox_requires_authentication_and_organization(setup):
    client, _ = setup
    register(client)
    client.cookies.clear()
    assert client.get("/api/inbox/conversations").status_code == 401


def test_integration_status_is_authorized_and_does_not_expose_secrets(setup):
    client, _ = setup
    register(client)
    response = client.get("/api/inbox/integration-status")
    assert response.status_code == 200
    status = response.json()
    assert status["database"]["backend"] == "sqlite"
    assert status["whatsapp"]["configured"] is False
    assert status["whatsapp"]["callback_path"] == "/webhooks/whatsapp"
    assert status["ai"]["automatic_confirmation"] is False
    assert "secret" not in response.text.lower()

    client.cookies.clear()
    assert client.get("/api/inbox/integration-status").status_code == 401


def test_webhook_verification_requires_token_and_registered_phone(setup, monkeypatch):
    client, _ = setup
    register(client)
    connect_phone(client)
    monkeypatch.setattr(settings, "whatsapp_verify_token", SecretStr("verify-secret"))

    path = "/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=verify-secret&hub.challenge=test123"
    assert client.get(path).text == "test123"
    assert client.get(path.replace("verify-secret", "wrong")).status_code == 403


def test_inbox_is_tenant_scoped_and_simulator_reuses_extraction(setup):
    client, factory = setup
    account = register(client)
    customer, product = catalog(client)
    phone = connect_phone(client)

    simulated = client.post(
        "/api/inbox/simulator",
        json={
            "phone_number_id": phone["phone_number_id"],
            "customer_phone": "+94770001122",
            "customer_name": "Nimal",
            "text": "Rice 2",
        },
    )
    assert simulated.status_code == 201, simulated.text
    assert simulated.json()["status"] == "processed"
    draft_id = simulated.json()["extraction_draft_id"]
    assert draft_id
    assert client.get("/api/orders").json() == []

    conversations = client.get("/api/inbox/conversations").json()
    assert len(conversations) == 1
    conversation = conversations[0]
    messages = client.get(
        f"/api/inbox/conversations/{conversation['id']}/messages"
    ).json()
    assert messages[0]["extraction_draft_id"] == draft_id
    draft = client.get(f"/api/extractions/{draft_id}").json()
    assert draft["result"]["items"][0]["product_id"] == product["id"]

    order = {
        "customer_id": customer["id"],
        "items": [{"product_id": product["id"], "quantity": 2}],
        "human_confirmed": True,
        "expected_total_minor": 50000,
        "flags_acknowledged": True,
        "draft_id": draft_id,
    }
    response = client.post(
        "/api/orders", json=order, headers={"Idempotency-Key": "whatsapp-order"}
    )
    assert response.status_code == 201, response.text
    assert response.json()["draft_id"] == draft_id

    original_org = account["organization_id"]
    other = register(client, "inbox-other")
    assert client.get("/api/inbox/conversations").json() == []
    client.headers["X-Organization-ID"] = original_org
    with factory() as db:
        stored_draft = db.get(ExtractionDraft, draft_id)
        assert stored_draft is not None
        assert db.scalar(select(WhatsAppPhoneNumber)) is not None
    assert other["organization_id"] != original_org
