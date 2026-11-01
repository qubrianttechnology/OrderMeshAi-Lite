from .conftest import register
from .test_business_billing import profile_data


def test_wholesale_categories_catalog_and_profile_are_validated_and_scoped(setup):
    client, _ = setup
    register(client, "wholesale")
    assert (
        client.get("/api/auth/me").json()["organizations"][0]["business_type"]
        == "wholesale"
    )
    categories = [
        "electronics",
        "fashion",
        "beauty",
        "grocery",
        "household",
        "packaging",
        "stationery",
        "hardware",
        "vehicle_parts",
    ]
    for index, category in enumerate(categories):
        response = client.post(
            "/api/products",
            json={
                "sku": f"ITEM-{index}",
                "name": category,
                "category": category,
                "price_minor": 12000,
                "unit": "cartons",
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["category"] == category
        assert response.json()["track_stock"] is True
    profile = {**profile_data("wholesale"), "primary_category": "vehicle_parts"}
    saved = client.put("/api/business-profile", json=profile)
    assert saved.status_code == 200
    assert saved.json()["profile"]["primary_category"] == "vehicle_parts"
    assert not client.get("/api/dashboard-preferences").json()["service_business"]
    assert (
        client.post(
            "/api/products",
            json={
                "sku": "BAD",
                "name": "Bad",
                "category": "invalid",
                "price_minor": 100,
            },
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/api/business-profile", json={**profile, "primary_category": "invalid"}
        ).status_code
        == 422
    )
    first_product = client.get("/api/products").json()[0]
    register(client, "other-wholesale")
    assert client.get("/api/products").json() == []
    assert (
        client.put(
            f"/api/products/{first_product['id']}",
            json={
                "sku": "FOREIGN",
                "name": "Foreign",
                "price_minor": 100,
                "category": "grocery",
            },
        ).status_code
        == 404
    )


def test_part_number_aliases_and_selling_units_are_preserved(setup):
    client, _ = setup
    register(client, "parts")
    product = client.post(
        "/api/products",
        json={
            "sku": "BRAKE-PAD",
            "name": "Brake pad",
            "category": "vehicle_parts",
            "aliases": ["OEM-04465"],
            "unit": "sets",
            "price_minor": 500000,
        },
    ).json()
    draft = client.post(
        "/api/extractions", json={"text": "OEM-04465 4", "language": "en"}
    )
    assert draft.status_code == 201, draft.text
    line = draft.json()["result"]["items"][0]
    assert line["product_id"] == product["id"] and line["quantity"] == 4
    assert client.get("/api/products").json()[0]["unit"] == "sets"
    updated = client.put(
        f"/api/products/{product['id']}",
        json={
            "sku": "BRAKE-PAD",
            "name": "Brake pad",
            "category": "hardware",
            "aliases": ["OEM-04465"],
            "unit": "sets",
            "price_minor": 500000,
        },
    )
    assert updated.status_code == 200 and updated.json()["category"] == "hardware"
