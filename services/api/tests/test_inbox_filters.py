from sqlalchemy import select

from app.models import WhatsAppMessage

from .conftest import register
from .test_whatsapp import connect_phone


def test_inbox_category_filters_search_and_tenant_isolation(setup):
    client, factory = setup
    register(client, "filter-owner")
    connect_phone(client)

    def message(phone, text, category):
        response = client.post(
            "/api/inbox/simulator",
            json={
                "phone_number_id": "123456789012345",
                "customer_phone": phone,
                "customer_name": "Filter customer",
                "text": text,
            },
        )
        assert response.status_code == 201, response.text
        data = response.json()
        with factory() as db:
            stored = db.scalar(
                select(WhatsAppMessage).where(
                    WhatsAppMessage.external_id == data["message_id"]
                )
            )
            data["message_id"] = stored.id
            data["conversation_id"] = stored.conversation_id
        changed = client.put(
            f"/api/inbox/messages/{data['message_id']}/category",
            json={"category": category},
        )
        assert changed.status_code == 200, changed.text
        return data

    private = message("+94770000001", "Birthday greeting needle-original", "personal")
    message("+94770000001", "Another greeting", "personal")
    spam = message("+94770000002", "Unwanted promotion", "spam")
    business = message("+94770000003", "Website consultation", "business_inquiry")
    for category, expected in [
        ("personal", private),
        ("spam", spam),
        ("business", business),
        ("business_inquiry", business),
    ]:
        response = client.get("/api/inbox/conversations", params={"category": category})
        assert response.status_code == 200
        assert [row["id"] for row in response.json()] == [expected["conversation_id"]]
    assert len(client.get("/api/inbox/conversations").json()) == 3
    assert (
        client.get(
            "/api/inbox/conversations", params={"category": "needs_review"}
        ).json()
        == []
    )
    found = client.get(
        "/api/inbox/conversations",
        params={"search": "needle-original", "category": "personal"},
    ).json()
    assert [row["id"] for row in found] == [private["conversation_id"]]
    assert (
        client.get(
            "/api/inbox/conversations",
            params={"category": "spam", "search": "needle-original"},
        ).json()
        == []
    )
    assert (
        client.get(
            "/api/inbox/conversations", params={"category": "invalid"}
        ).status_code
        == 422
    )
    message("+94770000003", "Private family conversation", "personal")
    filtered = client.get(
        "/api/inbox/conversations", params={"category": "business"}
    ).json()
    assert filtered[0]["last_message_preview"] == "Website consultation"
    register(client, "filter-other")
    for category in ("all", "business", "personal", "spam"):
        assert (
            client.get(
                "/api/inbox/conversations", params={"category": category, "search": ""}
            ).json()
            == []
        )
