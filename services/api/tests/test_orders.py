import pytest

from app.models import Organization

from .conftest import catalog, order_body, register


def test_confirm_idempotency_stock_cancel_invoice_analytics(setup):
    c, _ = setup
    register(c)
    customer, p = catalog(c)
    body = order_body(customer, p)
    r = c.post("/api/orders", json=body, headers={"Idempotency-Key": "order-key-1"})
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["total_minor"] == 50000
    assert c.get("/api/products").json()[0]["stock"] == 28
    assert (
        c.post(
            "/api/orders", json=body, headers={"Idempotency-Key": "order-key-1"}
        ).json()["id"]
        == order["id"]
    )
    assert c.get("/api/products").json()[0]["stock"] == 28
    body["items"][0]["quantity"] = 3
    assert (
        c.post(
            "/api/orders", json=body, headers={"Idempotency-Key": "order-key-1"}
        ).status_code
        == 409
    )
    pdf = c.get(f"/api/orders/{order['id']}/invoice")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    assert c.get("/api/analytics").json()["sales_minor"] == 50000
    for _ in range(2):
        assert (
            c.patch(
                f"/api/orders/{order['id']}", json={"status": "cancelled"}
            ).status_code
            == 200
        )
    assert c.get("/api/products").json()[0]["stock"] == 30
    assert c.get("/api/analytics").json()["sales_minor"] == 0
    assert (
        c.patch(f"/api/orders/{order['id']}", json={"status": "fulfilled"}).status_code
        == 409
    )


@pytest.mark.parametrize("quantity", [0, -1, 1.5, True, 100001])
def test_quantity_validation(setup, quantity):
    c, _ = setup
    register(c)
    customer, p = catalog(c)
    assert (
        c.post(
            "/api/orders",
            json=order_body(customer, p, quantity),
            headers={"Idempotency-Key": "invalid-order"},
        ).status_code
        == 422
    )


def test_confirmation_and_atomic_rollback(setup):
    c, _ = setup
    register(c)
    customer, p = catalog(c)
    body = order_body(customer, p)
    body["human_confirmed"] = False
    assert (
        c.post(
            "/api/orders", json=body, headers={"Idempotency-Key": "confirm-me"}
        ).status_code
        == 422
    )
    body["human_confirmed"] = True
    body["items"].append({"product_id": "missing", "quantity": 1})
    assert (
        c.post(
            "/api/orders", json=body, headers={"Idempotency-Key": "confirm-me"}
        ).status_code
        == 422
    )
    assert c.get("/api/products").json()[0]["stock"] == 30
    assert c.get("/api/orders").json() == []
    assert (
        c.post(
            "/api/orders",
            json=order_body(customer, p, 31),
            headers={"Idempotency-Key": "too-much-stock"},
        ).status_code
        == 409
    )


def test_extraction_confirmation_and_cross_tenant_access(setup):
    c, _ = setup
    register(c)
    customer, p = catalog(c)
    draft = c.post("/api/extractions", json={"text": "හාල් 2\nUnknown 3"}).json()
    assert draft["result"]["items"][0]["quantity"] == 2
    assert draft["result"]["items"][1]["product_id"] is None
    assert c.get("/api/orders").json() == []
    body = {**order_body(customer, p), "draft_id": draft["id"]}
    body["delivery_instructions"] = "deliver to Borella"
    assert (
        c.post(
            "/api/orders", json=body, headers={"Idempotency-Key": "draft-order"}
        ).status_code
        == 422
    )
    body["flags_acknowledged"] = True
    order = c.post(
        "/api/orders", json=body, headers={"Idempotency-Key": "draft-order"}
    ).json()
    assert order["delivery_instructions"] == "deliver to Borella"
    assert (
        c.post(
            "/api/orders", json=body, headers={"Idempotency-Key": "draft-again"}
        ).status_code
        == 409
    )
    register(c, "other")
    for url in [
        f"/api/orders/{order['id']}",
        f"/api/orders/{order['id']}/invoice",
        f"/api/extractions/{draft['id']}",
    ]:
        assert c.get(url).status_code == 404
    assert (
        c.post(
            "/api/orders", json=body, headers={"Idempotency-Key": "foreign-order"}
        ).status_code
        == 404
    )
    assert c.get("/api/analytics").json()["order_count"] == 0


def test_quota_and_subscription(setup):
    c, dbs = setup
    account = register(c)
    customer, p = catalog(c)
    with dbs() as db:
        org = db.get(Organization, account["organization_id"])
        org.monthly_order_limit = 0
        db.commit()
    assert (
        c.post(
            "/api/orders",
            json=order_body(customer, p),
            headers={"Idempotency-Key": "quota-test"},
        ).status_code
        == 409
    )
    with dbs() as db:
        org = db.get(Organization, account["organization_id"])
        org.monthly_order_limit = 500
        org.subscription_status = "past_due"
        db.commit()
    assert (
        c.post(
            "/api/orders",
            json=order_body(customer, p),
            headers={"Idempotency-Key": "billing-test"},
        ).status_code
        == 403
    )


def test_archived_product_and_duplicate_lines(setup):
    c, _ = setup
    register(c)
    customer, p = catalog(c)
    body = order_body(customer, p)
    body["items"] *= 2
    assert (
        c.post(
            "/api/orders", json=body, headers={"Idempotency-Key": "duplicate-lines"}
        ).status_code
        == 422
    )
    c.put(
        f"/api/products/{p['id']}",
        json={"sku": p["sku"], "name": p["name"], "price_minor": 1, "active": False},
    )
    assert (
        c.post(
            "/api/orders",
            json=order_body(customer, p),
            headers={"Idempotency-Key": "archived-product"},
        ).status_code
        == 422
    )


def test_stale_price_cannot_bypass_human_review(setup):
    c, _ = setup
    register(c)
    customer, p = catalog(c)
    body = order_body(customer, p)
    c.put(
        f"/api/products/{p['id']}",
        json={"sku": p["sku"], "name": p["name"], "price_minor": 30000},
    )
    assert (
        c.post(
            "/api/orders", json=body, headers={"Idempotency-Key": "price-changed"}
        ).status_code
        == 409
    )
    assert c.get("/api/orders").json() == []
