import hashlib
from datetime import timedelta
from urllib.parse import urlencode

from pydantic import SecretStr
from sqlalchemy import select

from app import billing, whatsapp
from app.models import (
    BillingCheckout,
    Organization,
    Product,
    StockMovement,
    as_utc,
    now,
)

from .conftest import catalog, order_body, register
from .test_whatsapp import connect_phone


def profile_data(business_type="software"):
    return {
        "business_type": business_type,
        "description": "We build websites and software applications for local companies.",
        "offerings": "Websites, hosting, software development and maintenance",
        "customers": "Small businesses and agencies",
        "workflow": "Inquiry -> requirements -> quote -> approval -> development -> delivery",
        "hours": "Monday to Friday 9 to 5",
        "payments": "Bank transfer with a 50% deposit",
        "delivery": "Remote delivery with agreed milestones",
        "exclusions": "lottery, personal parties",
    }


def test_profile_upload_permissions_and_tenant_isolation(setup):
    client, factory = setup
    account = register(client)
    response = client.put("/api/business-profile", json=profile_data())
    assert response.status_code == 200, response.text
    assert response.json()["ready"] is True
    upload = client.post(
        "/api/business-profile/document",
        content=b"We design and build websites for shops. Our workflow starts with a quotation.",
        headers={"X-Filename": "business.txt", "Content-Type": "text/plain"},
    )
    assert upload.status_code == 200
    assert upload.json()["profile"]["document_name"] == "business.txt"
    assert client.get("/api/business-profile/document-template").status_code == 200
    assert (
        client.post(
            "/api/business-profile/document",
            content=b"Bad content",
            headers={"X-Filename": "script.exe"},
        ).status_code
        == 415
    )
    assert (
        client.get(
            "/api/business-profile", headers={"X-Organization-ID": "other-tenant"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/business-profile/document",
            content=b"x" * 2_000_001,
            headers={"X-Filename": "large.txt"},
        ).status_code
        == 413
    )
    from app.models import Membership

    with factory() as db:
        membership = db.scalar(
            select(Membership).where(
                Membership.organization_id == account["organization_id"]
            )
        )
        membership.role = "viewer"
        db.commit()
    assert client.put("/api/business-profile", json=profile_data()).status_code == 403


def test_service_orders_do_not_require_or_mutate_stock(setup):
    client, factory = setup
    account = register(client)
    assert client.put("/api/business-profile", json=profile_data()).status_code == 200
    customer = client.post("/api/customers", json={"name": "Agency client"}).json()
    response = client.post(
        "/api/products",
        json={
            "name": "Website",
            "sku": "WEB",
            "price_minor": 100000,
            "unit": "project",
        },
    )
    assert response.status_code == 201, response.text
    product = response.json()
    assert product["track_stock"] is False and product["stock"] == 0
    assert (
        client.post(
            f"/api/products/{product['id']}/stock",
            json={"delta": 2, "reason": "Not stock"},
        ).status_code
        == 422
    )
    order = client.post(
        "/api/orders",
        json=order_body(customer, product, 1),
        headers={"Idempotency-Key": "service-order"},
    )
    assert order.status_code == 201, order.text
    # Turning tracking on later must not manufacture stock when the service is cancelled.
    with factory() as db:
        db.get(Product, product["id"]).track_stock = True
        db.commit()
    assert (
        client.patch(
            "/api/orders/" + order.json()["id"], json={"status": "cancelled"}
        ).status_code
        == 200
    )
    with factory() as db:
        assert db.get(Product, product["id"]).stock == 0
        assert (
            db.scalar(
                select(StockMovement).where(
                    StockMovement.organization_id == account["organization_id"]
                )
            )
            is None
        )


def test_trial_expiry_keeps_reads_and_renewal_available(setup):
    client, factory = setup
    account = register(client)
    info = client.get("/api/billing").json()
    assert info["amount_minor"] == 740000 and info["trial_days"] == 15
    with factory() as db:
        org = db.get(Organization, account["organization_id"])
        assert (
            timedelta(days=14, hours=23)
            < as_utc(org.trial_ends_at) - as_utc(org.trial_started_at)
            < timedelta(days=15, seconds=1)
        )
        org.trial_ends_at = now() - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/customers").status_code == 200
    assert client.get("/api/billing").json()["status"] == "expired"
    assert client.post("/api/customers", json={"name": "Blocked"}).status_code == 402
    assert client.put("/api/business-profile", json=profile_data()).status_code == 200
    assert client.get("/api/billing").json()["has_access"] is False


def test_inbox_filters_non_business_messages_and_allows_review(setup, monkeypatch):
    monkeypatch.setattr(whatsapp.settings, "ai_provider", "local")
    client, _ = setup
    register(client)
    catalog(client)
    connect_phone(client)
    for source, category in [
        ("Claim your prize lottery winner", "spam"),
        ("Happy birthday to you", "personal"),
        ("Is Rice available?", "business_inquiry"),
        ("Rice 2", "business_order"),
        ("Unclear unrelated subject", "needs_review"),
    ]:
        response = client.post(
            "/api/inbox/simulator",
            json={
                "phone_number_id": "123456789012345",
                "customer_phone": "+94770001122",
                "text": source,
            },
        )
        assert response.status_code == 201, response.text
        conversation = client.get("/api/inbox/conversations").json()[0]
        messages = client.get(
            "/api/inbox/conversations/" + conversation["id"] + "/messages"
        ).json()
        message = next(m for m in messages if m["text"] == source)
        assert message["category"] == category
        assert bool(message["extraction_draft_id"]) == (
            category in {"business_order", "business_inquiry"}
        )
    assert (
        client.put(
            "/api/inbox/messages/" + message["id"] + "/category",
            json={"category": "business_order"},
        ).status_code
        == 200
    )
    from app.models import WhatsAppWebhookEvent

    with setup[1]() as db:
        event = db.scalar(
            select(WhatsAppWebhookEvent).where(
                WhatsAppWebhookEvent.message_id == message["id"]
            )
        )
        assert event.status == "queued"


def configure_payhere(monkeypatch):
    for key, value in {
        "payhere_merchant_id": "test-merchant",
        "payhere_merchant_secret": SecretStr("test-secret"),
        "payhere_app_id": "test-app",
        "payhere_app_secret": SecretStr("test-app-secret"),
        "payhere_notify_url": "https://example.com/api/billing/payhere/notify",
        "payhere_sandbox": True,
    }.items():
        monkeypatch.setattr(billing.settings, key, value)


def checkout_body():
    return {
        "first_name": "Test",
        "last_name": "Owner",
        "phone": "0771234567",
        "address": "123 Test Street",
        "city": "Colombo",
        "consent_to_recurring": True,
    }


def notify_payload(order_id, amount="7400.00"):
    data = {
        "merchant_id": "test-merchant",
        "order_id": order_id,
        "payhere_amount": amount,
        "payhere_currency": "LKR",
        "status_code": "2",
        "payment_id": "untrusted-client-value",
        "subscription_id": "123456",
    }
    secret = hashlib.md5(b"test-secret").hexdigest().upper()
    raw = "test-merchant" + order_id + amount + "LKR2" + secret
    data["md5sig"] = hashlib.md5(raw.encode()).hexdigest().upper()
    return data


def test_payhere_signature_verification_replay_and_cancellation(setup, monkeypatch):
    configure_payhere(monkeypatch)
    client, factory = setup
    account = register(client)
    body = checkout_body()
    body["consent_to_recurring"] = False
    assert client.post("/api/billing/checkout", json=body).status_code == 422
    checkout = client.post("/api/billing/checkout", json=checkout_body())
    assert checkout.status_code == 200, checkout.text
    fields = checkout.json()["fields"]
    assert fields["amount"] == "7400.00" and fields["recurrence"] == "1 Month"
    assert "test-secret" not in checkout.text
    order_id = fields["order_id"]
    current = now().replace(microsecond=0)
    payments = [
        {
            "payment_id": "verified-payment",
            "order_id": order_id,
            "amount": 7400,
            "currency": "LKR",
            "status": "RECEIVED",
            "date": current.isoformat(),
        }
    ]

    def merchant(path, method="GET", body=None):
        if path.startswith("payment/search"):
            return payments
        if path == "subscription/cancel":
            assert method == "POST" and body["subscription_id"] == 123456
            return None
        return {"order_id": order_id, "subscription_id": "123456", "status": "ACTIVE"}

    monkeypatch.setattr(billing, "_merchant_call", merchant)
    payload = notify_payload(order_id)
    bad = {**payload, "md5sig": "0" * 32}
    assert (
        client.post(
            "/api/billing/payhere/notify",
            content=urlencode(bad),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        ).status_code
        == 403
    )

    def send(data):
        return client.post(
            "/api/billing/payhere/notify",
            content=urlencode(data),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    assert send(notify_payload(order_id, "1.00")).status_code == 422
    response = send(payload)
    assert response.status_code == 200, response.text
    before = client.get("/api/billing").json()
    assert before["has_access"] and before["status"] == "active"
    payload["payment_id"] = "another-forged-id"
    assert send(payload).status_code == 200
    assert client.get("/api/billing").json()["paid_until"] == before["paid_until"]
    with factory() as db:
        assert db.get(BillingCheckout, order_id).verified_payments == [
            "verified-payment"
        ]
    assert client.post("/api/billing/cancel").status_code == 200
    assert client.get("/api/billing").json()["status"] == "cancelled"
    # A chargeback verified by the gateway removes the paid entitlement.
    payments[0]["status"] = "CHARGEBACKED"
    assert send(payload).status_code == 200
    with factory() as db:
        assert db.get(Organization, account["organization_id"]).paid_until is None
