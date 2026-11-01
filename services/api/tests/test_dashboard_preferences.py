import pytest
from sqlalchemy import select

from app.models import Membership, Organization

from .conftest import register
from .test_business_billing import profile_data


def test_recommendations_follow_business_and_custom_layout_survives_profile_save(setup):
    client, _ = setup
    register(client)
    assert "orders" in client.get("/api/dashboard-preferences").json()["modules"]
    assert (
        client.put("/api/business-profile", json=profile_data("agency")).status_code
        == 200
    )
    prefs = client.get("/api/dashboard-preferences").json()
    assert prefs["service_business"] and prefs["customer_label"] == "Clients"
    assert "orders" not in prefs["modules"]
    changed = client.put("/api/dashboard-preferences", json={"modules": ["customers"]})
    assert changed.status_code == 200
    assert (
        client.put("/api/business-profile", json=profile_data("restaurant")).status_code
        == 200
    )
    prefs = client.get("/api/dashboard-preferences").json()
    assert prefs["modules"] == ["customers"] and prefs["catalog_label"] == "Menu"
    reset = client.put("/api/dashboard-preferences", json={"modules": None}).json()
    assert not reset["customized"] and "orders" in reset["modules"]
    assert client.get("/api/auth/me").json()["organizations"][0]["dashboard"] == reset
    assert (
        client.put(
            "/api/dashboard-preferences", json={"modules": ["admin"]}
        ).status_code
        == 422
    )
    assert (
        client.put("/api/dashboard-preferences", json={"modules": []}).status_code
        == 200
    )


@pytest.mark.parametrize(
    "kind,service",
    [("online_store", False), ("restaurant", False), ("salon", True), ("repair", True)],
)
def test_new_business_types_use_the_correct_extraction_and_stock_defaults(
    setup, kind, service
):
    client, _ = setup
    register(client)
    profile = client.put("/api/business-profile", json=profile_data(kind))
    assert profile.status_code == 200
    assert profile.json()["tracks_stock_by_default"] is not service
    assert (
        client.get("/api/dashboard-preferences").json()["service_business"] is service
    )
    if service:
        draft = client.post(
            "/api/extractions",
            json={
                "text": "Please arrange a repair visit on Friday",
                "language": "auto",
            },
        )
        assert draft.status_code == 201
        assert draft.json()["result"]["kind"] == "service_request"


def test_dashboard_isolation_roles_and_service_summary(setup):
    client, factory = setup
    first = register(client)
    for _ in range(2):
        assert (
            client.post(
                "/api/service-requests",
                json={
                    "text": "We need a website. Budget: LKR 50000",
                    "language": "auto",
                },
            ).status_code
            == 201
        )
    assert client.get("/api/dashboard-service-summary").json() == {
        "total": 2,
        "pending_review": 2,
        "accepted": 0,
        "completed": 0,
    }
    assert (
        client.put(
            "/api/dashboard-preferences", json={"modules": ["customers"]}
        ).status_code
        == 200
    )
    second = register(client, "second")
    assert client.get("/api/dashboard-service-summary").json()["total"] == 0
    assert client.get("/api/dashboard-preferences").json()["customized"] is False
    assert (
        client.put(
            "/api/dashboard-preferences",
            headers={"X-Organization-ID": first["organization_id"]},
            json={"modules": []},
        ).status_code
        == 403
    )
    with factory() as db:
        member = db.scalar(
            select(Membership).where(
                Membership.organization_id == second["organization_id"]
            )
        )
        member.role = "staff"
        db.commit()
    assert client.get("/api/dashboard-preferences").status_code == 200
    assert (
        client.put("/api/dashboard-preferences", json={"modules": []}).status_code
        == 403
    )
    with factory() as db:
        assert db.get(Organization, first["organization_id"]).business_profile[
            "dashboard"
        ]["modules"] == ["customers"]
