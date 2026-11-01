import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.config import settings
from app.models import (
    AuditEvent,
    ExtractionDraft,
    Organization,
    StockMovement,
    WhatsAppWebhookEvent,
)
from app.service_requests import extract_service_request, uses_service_workflow
from app.whatsapp import _extract_inbound_message

from .conftest import register
from .test_whatsapp import connect_phone

SOURCE = "We need a website with online booking; Budget: LKR 150,000; Deadline: 30 November; Meeting: Friday 2pm; Email: client@example.com"


@pytest.fixture(autouse=True)
def local_ai(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "local")


def test_service_lifecycle_persists_edits_and_blocks_stale_review(setup):
    client, factory = setup
    account = register(client)
    draft = client.post(
        "/api/service-requests", json={"text": SOURCE, "language": "auto"}
    ).json()
    assert draft["result"]["kind"] == "service_request"
    assert draft["result"]["service_request"]["request_type"] == "project"
    fields = draft["result"]["service_request"]
    assert fields["budget"] == "Budget: LKR 150,000"
    assert fields["deadline"] == "Deadline: 30 November"
    assert fields["appointment"] == "Meeting: Friday 2pm"
    assert fields["contact"] == "Email: client@example.com"
    assert draft["result"]["review"]["status"] == "pending_review"
    url = "/api/service-requests/" + draft["id"] + "/review"
    body = {
        "revision": 0,
        "status": "accepted",
        "fields": {**fields, "budget": "Client confirmed LKR 140,000"},
        "notes": "Await deposit",
        "human_confirmed": True,
    }
    assert client.put(url, json={**body, "human_confirmed": False}).status_code == 422
    assert client.put(url, json={**body, "status": "completed"}).status_code == 422
    accepted = client.put(url, json=body)
    assert accepted.status_code == 200, accepted.text
    assert (
        accepted.json()["result"]["review"]["fields"]["budget"]
        == "Client confirmed LKR 140,000"
    )
    assert accepted.json()["result"]["service_request"]["budget"] == fields["budget"]
    assert client.put(url, json=body).status_code == 409
    completed = client.put(url, json={**body, "revision": 1, "status": "completed"})
    assert completed.status_code == 200
    assert client.put(url, json={**body, "revision": 2}).status_code == 409
    assert (
        client.get("/api/service-requests").json()[0]["result"]["review"]["status"]
        == "completed"
    )
    with factory() as db:
        assert db.scalar(select(StockMovement)) is None
        assert (
            len(
                db.scalars(
                    select(AuditEvent).where(
                        AuditEvent.action.like("service_request.%")
                    )
                ).all()
            )
            == 3
        )
    register(client, "other")
    assert client.get("/api/service-requests").json() == []
    assert client.put(url, json=body).status_code == 404
    assert client.get("/api/extractions/" + draft["id"]).status_code == 404
    with factory() as db:
        assert (
            db.get(ExtractionDraft, draft["id"]).organization_id
            == account["organization_id"]
        )


def test_software_manual_extraction_and_no_invented_details(setup):
    client, factory = setup
    account = register(client)
    with factory() as db:
        db.get(Organization, account["organization_id"]).business_type = "software"
        db.commit()
    response = client.post(
        "/api/extractions",
        json={"text": "We need an inventory app", "language": "auto"},
    )
    assert response.status_code == 201, response.text
    result = response.json()["result"]
    assert result["kind"] == "service_request" and result["items"] == []
    assert result["service_request"]["requirements"] == ["We need an inventory app"]
    assert result["service_request"]["budget"] is None
    assert set(result["missing_fields"]) == {
        "budget",
        "deadline",
        "appointment",
        "contact",
    }


def test_service_whatsapp_inquiry_not_spam_creates_request_once(setup):
    client, factory = setup
    account = register(client)
    with factory() as db:
        org = db.get(Organization, account["organization_id"])
        org.business_type = "agency"
        org.business_profile = {
            "description": "We build websites and manage marketing campaigns"
        }
        db.commit()
    connect_phone(client)
    for text in [
        SOURCE,
        "Happy birthday to you",
        "Claim your prize lottery winner",
        "Unknown unrelated thing",
    ]:
        r = client.post(
            "/api/inbox/simulator",
            json={
                "phone_number_id": "123456789012345",
                "customer_phone": "+94770001122",
                "text": text,
            },
        )
        assert r.status_code == 201, r.text
    drafts = client.get("/api/service-requests").json()
    assert len(drafts) == 1 and drafts[0]["source_text"] == SOURCE
    with factory() as db:
        event = db.scalar(
            select(WhatsAppWebhookEvent)
            .where(WhatsAppWebhookEvent.organization_id == account["organization_id"])
            .order_by(WhatsAppWebhookEvent.created_at)
        )
        _extract_inbound_message(db, event)
        db.commit()
        assert len(db.scalars(select(ExtractionDraft)).all()) == 1


def test_service_provider_grounding_and_safe_fallback(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", SecretStr("test-key"))
    org = SimpleNamespace(business_type="software")
    fields = {
        "request_type": "project",
        "requirements": ["We need a website with online booking"],
        "budget": "Budget: LKR 150,000",
        "deadline": "Deadline: 30 November",
        "appointment": "Meeting: Friday 2pm",
        "contact": "Email: client@example.com",
    }

    def transport(output):
        def handle(request):
            payload = json.loads(request.content)
            assert payload["store"] is False
            exported = json.loads(payload["input"])
            assert set(exported) == {"business_type", "customer_message"}
            assert payload["text"]["format"]["schema"]["additionalProperties"] is False
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "output": [
                        {
                            "content": [
                                {"type": "output_text", "text": json.dumps(output)}
                            ]
                        }
                    ],
                },
            )

        return httpx.MockTransport(handle)

    result = extract_service_request(SOURCE, org, transport(fields))
    assert result["provider"] == "openai-structured-v1"
    assert result["service_request"] == fields
    bad = extract_service_request(
        SOURCE, org, transport({**fields, "budget": "USD 99999"})
    )
    assert bad["provider"] == "local-rules-v1"
    assert "ai_provider_fallback" in bad["flags"]
    assert bad["service_request"]["budget"] == "Budget: LKR 150,000"
    unavailable = extract_service_request(
        SOURCE,
        org,
        httpx.MockTransport(
            lambda _: httpx.Response(401, json={"error": "secret response"})
        ),
    )
    assert "ai_provider_fallback" in unavailable["flags"]
    assert "secret response" not in json.dumps(unavailable)


def test_hybrid_routes_tracked_items_to_orders_and_services_to_requests():
    org = SimpleNamespace(business_type="hybrid")
    goods = SimpleNamespace(name="Laptop", sku="L1", aliases=[], track_stock=True)
    service = SimpleNamespace(
        name="Consultation", sku="C1", aliases=[], track_stock=False
    )
    assert not uses_service_workflow(org, [goods, service], "Laptop 2")
    assert uses_service_workflow(org, [goods, service], "Consultation Friday 2pm")
    assert not uses_service_workflow(org, [goods, service], "Laptop 2 and Consultation")


def test_request_viewer_and_subscription_cannot_mutate(setup):
    from datetime import timedelta

    from app.models import Membership, now

    client, factory = setup
    account = register(client)
    draft = client.post(
        "/api/service-requests", json={"text": SOURCE, "language": "auto"}
    ).json()
    fields = draft["result"]["service_request"]
    url = "/api/service-requests/" + draft["id"] + "/review"
    body = {
        "revision": 0,
        "status": "accepted",
        "fields": fields,
        "human_confirmed": True,
    }
    with factory() as db:
        membership = db.scalar(
            select(Membership).where(
                Membership.organization_id == account["organization_id"]
            )
        )
        membership.role = "viewer"
        db.commit()
    assert client.get("/api/service-requests").status_code == 200
    assert (
        client.post(
            "/api/service-requests", json={"text": SOURCE, "language": "auto"}
        ).status_code
        == 403
    )
    assert client.put(url, json=body).status_code == 403
    with factory() as db:
        membership = db.scalar(
            select(Membership).where(
                Membership.organization_id == account["organization_id"]
            )
        )
        membership.role = "owner"
        db.get(Organization, account["organization_id"]).trial_ends_at = (
            now() - timedelta(seconds=1)
        )
        db.commit()
    assert client.get("/api/service-requests").status_code == 200
    assert client.put(url, json=body).status_code == 402


def test_dates_are_not_contact_numbers_and_service_drafts_cannot_confirm_orders(setup):
    client, _ = setup
    register(client)
    draft = client.post(
        "/api/service-requests", json={"text": "Need a website; Deadline: 2026-11-30"}
    ).json()
    assert draft["result"]["service_request"]["contact"] is None
    customer = client.post("/api/customers", json={"name": "Service Client"}).json()
    product = client.post(
        "/api/products",
        json={
            "name": "Website",
            "sku": "WEB",
            "price_minor": 10000,
            "track_stock": False,
        },
    ).json()
    response = client.post(
        "/api/orders",
        json={
            "customer_id": customer["id"],
            "items": [{"product_id": product["id"], "quantity": 1}],
            "human_confirmed": True,
            "flags_acknowledged": True,
            "draft_id": draft["id"],
            "expected_total_minor": 10000,
        },
        headers={"Idempotency-Key": "blocked-service-draft"},
    )
    assert (
        response.status_code == 422 and "service requests" in response.json()["detail"]
    )
    assert client.get("/api/orders").json() == []
