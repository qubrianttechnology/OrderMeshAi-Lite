"""Accounting/stock invariants, authorization and rollback for distribution workflows."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.models import CustomerPayment, Membership, Order, WarehouseBalance

from .conftest import catalog, order_body, register


def post(c, path, body, key="unique-test-key"):
    return c.post("/api/commerce" + path, json=body, headers={"Idempotency-Key": key})


def setup_sale(c):
    user = register(c)
    customer, product = catalog(c)
    update = {
        k: v
        for k, v in product.items()
        if k
        in {
            "name",
            "sku",
            "aliases",
            "unit",
            "price_minor",
            "reorder_level",
            "active",
            "category",
            "track_stock",
        }
    }
    update.update(
        cost_minor=15000,
        wholesale_price_minor=20000,
        wholesale_min_qty=5,
        barcode="RICE001",
        min_order_qty=1,
    )
    assert c.put("/api/products/" + product["id"], json=update).status_code == 200
    sale = {
        **order_body(customer, product),
        "paid_minor": 50000,
        "payment_method": "cash",
    }
    return user, customer, product, sale


def test_pos_pricing_payment_idempotency_pdf_and_report(setup):
    c, factory = setup
    _, customer, p, s = setup_sale(c)
    s.update(
        items=[{"product_id": p["id"], "quantity": 5}],
        price_mode="wholesale",
        discount_minor=1000,
        tax_basis_points=1000,
        expected_total_minor=108900,
        paid_minor=108900,
    )
    response = post(c, "/sales", s)
    assert response.status_code == 201, response.text
    order = response.json()
    assert (
        order["subtotal_minor"] == 100000
        and order["tax_minor"] == 9900
        and order["financial_posted"]
    )
    assert post(c, "/sales", s).json()["id"] == order["id"]
    assert post(c, "/sales", {**s, "payment_method": "card"}).status_code == 409
    assert c.get("/api/products").json()[0]["stock"] == 25
    with factory() as db:
        assert len(list(db.scalars(select(CustomerPayment)))) == 1
        assert sum(x.quantity for x in db.scalars(select(WarehouseBalance))) == 25
    assert c.get("/api/orders/" + order["id"] + "/invoice").content.startswith(b"%PDF")
    day = datetime.now(ZoneInfo("Asia/Colombo")).date()
    report = c.get(f"/api/commerce/reports?start={day}&end={day}").json()
    assert (
        report["net_sales_minor"] == 99000
        and report["cost_of_sales_minor"] == 75000
        and report["net_profit_minor"] == 24000
    )


def test_pos_failed_credit_and_stale_prices_are_atomic(setup):
    c, factory = setup
    _, _, p, s = setup_sale(c)
    assert (
        post(
            c, "/sales", {**s, "paid_minor": 0, "payment_method": "credit"}
        ).status_code
        == 409
    )
    assert (
        post(
            c, "/sales", {**s, "expected_total_minor": 1}, "stale-price-key"
        ).status_code
        == 409
    )
    assert (
        post(c, "/sales", {**s, "paid_minor": 60000}, "over-payment-key").status_code
        == 422
    )
    assert (
        post(
            c, "/sales", {**s, "human_confirmed": 1}, "numeric-confirm-key"
        ).status_code
        == 422
    )
    assert c.get("/api/products").json()[0]["stock"] == 30
    assert c.get("/api/orders").json() == []
    with factory() as db:
        assert list(db.scalars(select(CustomerPayment))) == []


def test_credit_limit_aging_and_payment_no_second_deduction(setup):
    c, factory = setup
    _, customer, p, s = setup_sale(c)
    assert (
        c.put(
            "/api/customers/" + customer["id"],
            json={
                "name": customer["name"],
                "credit_limit_minor": 80000,
                "payment_terms_days": 0,
            },
        ).status_code
        == 200
    )
    r = post(c, "/sales", {**s, "paid_minor": 0, "payment_method": "credit"})
    assert r.status_code == 201, r.text
    oid = r.json()["id"]
    assert (
        post(
            c,
            "/sales",
            {**s, "paid_minor": 0, "payment_method": "credit"},
            "second-credit-key",
        ).status_code
        == 409
    )
    with factory() as db:
        order = db.get(Order, oid)
        order.due_date = datetime.now(ZoneInfo("Asia/Colombo")).date() - timedelta(
            days=32
        )
        db.commit()
    a = c.get("/api/commerce/accounts").json()[0]
    assert (
        a["outstanding_minor"] == 50000
        and a["overdue_minor"] == 50000
        and a["orders"][0]["days_overdue"] == 32
    )
    pay = {"amount_minor": 20000, "method": "bank_transfer", "reference": "TEST"}
    assert (
        post(c, f"/orders/{oid}/payments", pay, "payment-once-key").status_code == 201
    )
    assert (
        post(c, f"/orders/{oid}/payments", pay, "payment-once-key").status_code == 201
    )
    assert c.get("/api/products").json()[0]["stock"] == 28
    assert c.get("/api/commerce/accounts").json()[0]["outstanding_minor"] == 30000
    assert (
        post(
            c, f"/orders/{oid}/payments", {"amount_minor": 30001}, "payment-too-much"
        ).status_code
        == 422
    )
    assert (
        c.patch("/api/orders/" + oid, json={"status": "cancelled"}).status_code == 409
    )


def test_purchase_grn_weighted_cost_transfer_and_warehouse_sale(setup):
    c, _ = setup
    _, _, p, s = setup_sale(c)
    supplier = post(c, "/suppliers", {"name": "Demo supplier"}).json()
    main = c.get("/api/commerce/warehouses").json()[0]
    second = post(
        c, "/warehouses", {"name": "Distribution depot", "code": "DEPOT"}
    ).json()
    po = post(
        c,
        "/purchases",
        {
            "supplier_id": supplier["id"],
            "warehouse_id": second["id"],
            "items": [{"product_id": p["id"], "quantity": 10, "cost_minor": 17000}],
        },
    ).json()
    assert c.get("/api/products").json()[0]["stock"] == 30
    for _ in range(2):
        assert (
            c.patch(
                "/api/commerce/purchases/" + po["id"], json={"status": "received"}
            ).status_code
            == 200
        )
    product = c.get("/api/products").json()[0]
    assert product["stock"] == 40 and product["cost_minor"] == 15500
    transfer = {
        "product_id": p["id"],
        "from_warehouse_id": main["id"],
        "to_warehouse_id": second["id"],
        "quantity": 5,
    }
    for _ in range(2):
        assert post(c, "/transfers", transfer, "transfer-once-key").status_code == 201
    assert c.get("/api/products").json()[0]["stock"] == 40
    assert (
        c.get("/api/commerce/stock?warehouse_id=" + second["id"]).json()[0]["quantity"]
        == 15
    )
    assert (
        post(
            c, "/transfers", {**transfer, "quantity": 99}, "invalid-transfer"
        ).status_code
        == 409
    )
    assert (
        post(
            c, "/sales", {**s, "warehouse_id": second["id"]}, "depot-sale-key"
        ).status_code
        == 201
    )
    assert (
        c.get("/api/commerce/stock?warehouse_id=" + second["id"]).json()[0]["quantity"]
        == 13
    )
    assert (
        c.get("/api/commerce/stock?warehouse_id=" + main["id"]).json()[0]["quantity"]
        == 25
    )


def test_returns_proration_stock_refund_and_profit(setup):
    c, _ = setup
    _, _, p, s = setup_sale(c)
    s.update(
        discount_minor=1000,
        tax_basis_points=1000,
        expected_total_minor=53900,
        paid_minor=53900,
    )
    oid = post(c, "/sales", s).json()["id"]
    body = {
        "items": [{"product_id": p["id"], "quantity": 1, "resellable": True}],
        "reason": "Customer return",
        "refund_minor": 26950,
    }
    result = post(c, f"/orders/{oid}/returns", body, "return-once-key")
    assert result.status_code == 201, result.text
    assert result.json()["total_minor"] == 26950
    assert (
        post(c, f"/orders/{oid}/returns", body, "return-once-key").json()["id"]
        == result.json()["id"]
    )
    assert c.get("/api/products").json()[0]["stock"] == 29
    assert (
        post(
            c,
            f"/orders/{oid}/returns",
            {**body, "refund_minor": 26951},
            "over-refund-key",
        ).status_code
        == 422
    )
    assert c.get("/api/products").json()[0]["stock"] == 29
    assert (
        post(c, f"/orders/{oid}/returns", body, "return-second-key").status_code == 201
    )
    assert c.get("/api/products").json()[0]["stock"] == 30
    assert (
        post(c, f"/orders/{oid}/returns", body, "return-third-key").status_code == 422
    )
    day = datetime.now(ZoneInfo("Asia/Colombo")).date()
    report = c.get(f"/api/commerce/reports?start={day}&end={day}").json()
    assert (
        report["net_sales_minor"] == 0
        and report["cost_of_sales_minor"] == 0
        and report["refunds_paid_minor"] == 53900
    )


def test_expense_void_unknown_cost_and_unposted_order_reporting(setup):
    c, _ = setup
    register(c)
    customer, p = catalog(c)
    oid = c.post(
        "/api/orders",
        json=order_body(customer, p),
        headers={"Idempotency-Key": "manual-order-key"},
    ).json()["id"]
    day = datetime.now(ZoneInfo("Asia/Colombo")).date()
    url = f"/api/commerce/reports?start={day}&end={day}"
    assert (
        c.get(url).json()["unposted_orders"] == 1
        and c.get(url).json()["sales_count"] == 0
    )
    assert (
        post(
            c, f"/orders/{oid}/payments", {"amount_minor": 50000}, "pay-manual-order"
        ).status_code
        == 201
    )
    body = {
        "category": "Transport",
        "description": "Demo transport",
        "amount_minor": 1000,
        "paid_on": str(day),
    }
    e = post(c, "/expenses", body).json()
    assert post(c, "/expenses", body).json()["id"] == e["id"]
    r = c.get(url).json()
    assert (
        r["expenses_minor"] == 1000
        and r["net_profit_minor"] is None
        and r["missing_cost_lines"] == 1
    )
    c.delete("/api/commerce/expenses/" + e["id"])
    assert c.get(url).json()["expenses_minor"] == 0


def test_commerce_tenant_isolation_and_staff_viewer_permissions(setup):
    c, factory = setup
    first, _, p, s = setup_sale(c)
    oid = post(c, "/sales", s).json()["id"]
    warehouse = c.get("/api/commerce/warehouses").json()[0]["id"]
    second = register(c, "second-commerce")
    assert c.get("/api/commerce/stock?warehouse_id=" + warehouse).status_code == 404
    assert (
        post(
            c, f"/orders/{oid}/payments", {"amount_minor": 1}, "cross-org-pay-key"
        ).status_code
        == 404
    )
    assert c.get("/api/commerce/accounts").json() == []
    with factory() as db:
        db.add(
            Membership(
                user_id=second["id"],
                organization_id=first["organization_id"],
                role="staff",
            )
        )
        db.commit()
    c.headers["X-Organization-ID"] = first["organization_id"]
    assert post(c, "/suppliers", {"name": "No access"}).status_code == 403
    assert (
        c.get("/api/commerce/reports?start=2026-01-01&end=2026-01-02").status_code
        == 403
    )
    assert post(c, "/sales", s, "staff-sale-key").status_code == 201
    with factory() as db:
        m = db.get(Membership, (second["id"], first["organization_id"]))
        m.role = "viewer"
        db.commit()
    assert post(c, "/sales", s, "viewer-sale-key").status_code == 403
    assert (
        c.put(
            "/api/commerce/team", json={"email": "one@example.com", "role": "admin"}
        ).status_code
        == 403
    )


def test_delivery_and_team_no_stock_rededuction(setup):
    c, _ = setup
    _, _, p, s = setup_sale(c)
    oid = post(c, "/sales", s).json()["id"]
    assert (
        c.put(
            f"/api/commerce/orders/{oid}/delivery", json={"status": "delivered"}
        ).status_code
        == 200
    )
    assert c.get("/api/products").json()[0]["stock"] == 28
    owner = c.get("/api/commerce/team").json()[0]
    assert c.delete("/api/commerce/team/" + owner["user_id"]).status_code == 409
    assert (
        c.put(
            f"/api/commerce/orders/{oid}/delivery",
            json={"status": "dispatched", "assigned_to": "foreign-member"},
        ).status_code
        == 422
    )


def test_delayed_refunds_tax_rounding_and_receipt(setup):
    c, _ = setup
    _, _, p, s = setup_sale(c)
    s.update(
        items=[{"product_id": p["id"], "quantity": 3}],
        discount_minor=1,
        tax_basis_points=1700,
        expected_total_minor=87749,
        paid_minor=87749,
    )
    sale = post(c, "/sales", s)
    assert sale.status_code == 201, sale.text
    oid = sale.json()["id"]
    for index in range(3):
        r = post(
            c,
            f"/orders/{oid}/returns",
            {
                "items": [{"product_id": p["id"], "quantity": 1}],
                "reason": "Demo return",
            },
            f"round-return-{index}",
        )
        assert r.status_code == 201, r.text
    refunds = {"amount_minor": 87749, "method": "cash"}
    r = post(c, f"/orders/{oid}/refunds", refunds, "late-refund-key")
    assert r.status_code == 201, r.text
    assert (
        post(c, f"/orders/{oid}/refunds", refunds, "late-refund-key").json()["id"]
        == r.json()["id"]
    )
    assert (
        post(
            c, f"/orders/{oid}/refunds", {"amount_minor": 1}, "extra-refund-key"
        ).status_code
        == 422
    )
    assert c.get(f"/api/commerce/orders/{oid}/receipt").content.startswith(b"%PDF")
    day = datetime.now(ZoneInfo("Asia/Colombo")).date()
    report = c.get(f"/api/commerce/reports?start={day}&end={day}").json()
    assert report["net_sales_minor"] == 0 and report["net_profit_minor"] == 0


def test_large_catalog_exact_multilingual_and_unknown_local():
    from types import SimpleNamespace

    from app.extraction import LocalExtractor

    products = [
        SimpleNamespace(
            id=f"p{x}", name=f"Demo item {x:04d}", sku=f"SKU{x:04d}", aliases=[]
        )
        for x in range(3000)
    ]
    products[0].aliases = ["හාල්", "அரிசி"]
    for source in ["SKU0000 2", "හාල් 2", "அரிசி 2"]:
        result = LocalExtractor().extract(source, "auto", products)
        assert (
            result.items[0].product_id == "p0"
            and result.items[0].quantity == 2
            and result.requires_confirmation
        )
    assert (
        LocalExtractor()
        .extract("Unknown product 5", "en", products)
        .items[0]
        .product_id
        is None
    )


def test_large_catalog_model_context_is_bounded_to_grounded_candidates():
    import json
    from types import SimpleNamespace

    import httpx

    from app.ai_provider import OpenAIExtractor

    products = [
        SimpleNamespace(
            id=f"p{x}",
            name=f"Demo item {x:04d}",
            sku=f"SKU{x:04d}",
            aliases=[],
            unit="units",
        )
        for x in range(3000)
    ]

    def handler(request):
        context = json.loads(json.loads(request.content)["input"])
        assert len(context["catalog"]) == 1 and context["catalog"][0]["id"] == "p2999"
        result = {
            "language": "en",
            "items": [
                {
                    "source": "SKU2999 2",
                    "product_id": "p2999",
                    "product_name": "Demo item 2999",
                    "quantity": 2,
                    "unit": None,
                    "confidence": 0.9,
                    "flags": [],
                }
            ],
            "flags": [],
            "delivery_instructions": None,
        }
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {"content": [{"type": "output_text", "text": json.dumps(result)}]}
                ],
            },
        )

    result = OpenAIExtractor(
        "test-key", "configured-model", httpx.MockTransport(handler)
    ).extract("SKU2999 2", "en", products)
    assert (
        result.provider == "openai-structured-v1"
        and result.items[0].product_id == "p2999"
    )
