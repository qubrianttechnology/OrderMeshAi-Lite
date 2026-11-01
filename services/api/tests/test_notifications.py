from sqlalchemy import select

from app.models import Membership, NotificationRead

from .conftest import catalog, register
from .test_whatsapp import connect_phone


def test_notification_sources_read_state_recurrence_and_isolation(setup):
    client, factory = setup
    first = register(client)
    _, product = catalog(client)
    assert client.get("/api/notifications").json()["unread_count"] == 0
    client.post(
        f"/api/products/{product['id']}/stock",
        json={"delta": -25, "reason": "Stock sale"},
    )
    feed = client.get("/api/notifications").json()
    assert feed["unread_count"] == 1 and feed["items"][0]["title"] == "Low stock"
    old = feed["items"][0]["id"]
    assert (
        client.post("/api/notifications/read", json={"keys": [old]}).json()[
            "marked_read"
        ]
        == 1
    )
    assert (
        client.post("/api/notifications/read", json={"all": True}).json()["marked_read"]
        == 0
    )
    assert client.get("/api/notifications").json()["unread_count"] == 0
    client.post(
        f"/api/products/{product['id']}/stock", json={"delta": 20, "reason": "Restock"}
    )
    assert client.get("/api/notifications").json()["items"] == []
    client.post(
        f"/api/products/{product['id']}/stock",
        json={"delta": -20, "reason": "Stock sale again"},
    )
    assert client.get("/api/notifications").json()["items"][0]["id"] != old
    second = register(client, "second-alert-user")
    assert client.get("/api/notifications").json()["items"] == []
    assert (
        client.post("/api/notifications/read", json={"keys": [old]}).json()[
            "marked_read"
        ]
        == 0
    )
    with factory() as db:
        db.add(
            Membership(
                user_id=second["id"],
                organization_id=first["organization_id"],
                role="viewer",
            )
        )
        db.commit()
    client.headers["X-Organization-ID"] = first["organization_id"]
    assert client.get("/api/notifications").json()["unread_count"] == 1
    with factory() as db:
        assert len(list(db.scalars(select(NotificationRead)))) == 1


def test_inbox_and_service_requests_produce_actionable_alerts(setup):
    client, _ = setup
    register(client)
    connect_phone(client)
    client.post(
        "/api/inbox/simulator",
        json={
            "phone_number_id": "123456789012345",
            "customer_phone": "+94770001122",
            "text": "Hello",
        },
    )
    feed = client.get("/api/notifications").json()
    assert any(item["target"] == "WhatsApp inbox" for item in feed["items"])
    conversation = client.get("/api/inbox/conversations").json()[0]
    client.get(f"/api/inbox/conversations/{conversation['id']}/messages")
    assert not any(
        item["target"] == "WhatsApp inbox"
        for item in client.get("/api/notifications").json()["items"]
    )
    created = client.post(
        "/api/service-requests",
        json={"text": "We need a website. Budget LKR 50000.", "language": "en"},
    )
    assert created.status_code == 201
    assert any(
        item["target"] == "Service requests"
        for item in client.get("/api/notifications").json()["items"]
    )
