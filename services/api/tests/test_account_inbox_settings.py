from io import BytesIO

from PIL import Image
from sqlalchemy import select

from app.models import Membership, Organization

from .conftest import register
from .test_whatsapp import connect_phone


def test_profile_photo_is_private_normalized_and_removable(setup):
    client, _ = setup
    register(client, "profile")
    assert (
        client.put(
            "/api/auth/profile", json={"name": "New name", "phone": "+94 77 000 0000"}
        ).status_code
        == 200
    )
    assert client.get("/api/auth/me").json()["name"] == "New name"
    image = BytesIO()
    Image.new("RGBA", (600, 300), (20, 40, 60, 80)).save(image, format="PNG")
    assert (
        client.put(
            "/api/auth/profile/photo",
            content=image.getvalue(),
            headers={"Content-Type": "image/png"},
        ).status_code
        == 200
    )
    result = client.get("/api/auth/profile/photo")
    assert result.headers["cache-control"] == "no-store"
    with Image.open(BytesIO(result.content)) as photo:
        assert photo.format == "JPEG" and photo.size == (256, 128)
    assert client.put("/api/auth/profile/photo", content=b"<svg/>").status_code == 422
    assert client.get("/api/auth/profile").json()["has_photo"] is True
    register(client, "another-profile")
    assert client.get("/api/auth/profile/photo").status_code == 404
    assert client.get("/api/auth/profile").json()["name"] == "Test User"
    assert client.delete("/api/auth/profile/photo").status_code == 204


def test_workspace_basics_and_full_layout_preserve_business_workflow(setup):
    client, factory = setup
    account = register(client, "basics")
    org_id = account["organization_id"]
    with factory() as db:
        org = db.get(Organization, org_id)
        org.business_type = "software"
        org.business_profile = {"description": "Software projects"}
        db.commit()
    body = {
        "name": "Software Studio",
        "contact_phone": "+94770000000",
        "contact_email": "office@example.com",
        "address": "Colombo",
    }
    assert client.put("/api/workspace/basic-settings", json=body).status_code == 200
    assert client.get("/api/workspace/basic-settings").json()["name"] == body["name"]
    result = client.put(
        "/api/dashboard-preferences", json={"layout": "full", "modules": None}
    ).json()
    assert result["full_business_tools"] and result["service_business"]
    assert set(result["modules"]) == {
        "orders",
        "service_requests",
        "customers",
        "catalog",
    }
    with factory() as db:
        org = db.get(Organization, org_id)
        assert (
            org.business_type == "software"
            and org.business_profile["description"] == "Software projects"
        )
        member = db.scalar(
            select(Membership).where(Membership.organization_id == org_id)
        )
        member.role = "viewer"
        db.commit()
    assert client.put("/api/workspace/basic-settings", json=body).status_code == 403
    assert (
        client.put(
            "/api/auth/profile", json={"name": "Viewer name", "phone": ""}
        ).status_code
        == 200
    )
    register(client, "unrelated-basics")
    assert client.get("/api/workspace/basic-settings").json()["name"] != body["name"]


def test_inbox_management_filters_polling_and_incoming_reopen(setup):
    client, factory = setup
    account = register(client, "manage-inbox")
    connect_phone(client)

    def incoming(text="Synthetic business question"):
        result = client.post(
            "/api/inbox/simulator",
            json={
                "phone_number_id": "123456789012345",
                "customer_phone": "+94770000001",
                "customer_name": "Sample customer",
                "text": text,
            },
        )
        assert result.status_code == 201

    incoming()
    row = client.get("/api/inbox/conversations").json()[0]
    path = f"/api/inbox/conversations/{row['id']}"
    assert (
        client.patch(
            path + "/management", json={"pinned": True, "archived": True}
        ).status_code
        == 200
    )
    assert client.get("/api/inbox/conversations?view=active").json() == []
    archived = client.get("/api/inbox/conversations?view=archived").json()
    assert archived[0]["pinned"] is True
    client.get(path + "/messages?mark_read=false")
    assert client.get("/api/inbox/conversations").json()[0]["unread_count"] == 1
    client.get(path + "/messages")
    assert client.get("/api/inbox/conversations").json()[0]["unread_count"] == 0
    client.patch(path + "/management", json={"read_state": "unread"})
    incoming("A new synthetic message")
    active = client.get("/api/inbox/conversations?view=unread").json()
    assert active[0]["archived"] is False and active[0]["unread_count"] == 2
    assert client.patch(path + "/management", json={}).status_code == 422
    with factory() as db:
        member = db.scalar(
            select(Membership).where(
                Membership.organization_id == account["organization_id"]
            )
        )
        member.role = "viewer"
        db.commit()
    assert client.patch(path + "/management", json={"pinned": False}).status_code == 403
    register(client, "unrelated-inbox")
    assert client.patch(path + "/management", json={"pinned": False}).status_code == 404
