from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.models import Membership, Order

from .conftest import catalog, order_body, register
from .test_commerce import post, setup_sale


def test_dashboard_charts_match_financial_report_returns_and_inventory(setup):
    c, _ = setup
    user, _, p, body = setup_sale(c)
    sale = post(c, "/sales", body).json()
    r = post(
        c,
        f"/orders/{sale['id']}/returns",
        {
            "items": [{"product_id": p["id"], "quantity": 1}],
            "reason": "Resellable return",
            "refund_minor": 25000,
        },
        "chart-return-key",
    )
    assert r.status_code == 201, r.text
    day = str(datetime.now(ZoneInfo("Asia/Colombo")).date())
    assert (
        post(
            c,
            "/expenses",
            {
                "category": "Delivery",
                "description": "Delivery cost",
                "amount_minor": 1000,
                "paid_on": day,
            },
            "chart-expense-key",
        ).status_code
        == 201
    )
    c.post(
        f"/api/products/{p['id']}/stock",
        json={"delta": -25, "reason": "Inventory count"},
    )
    response = c.get("/api/commerce/dashboard-insights?days=30")
    assert response.status_code == 200, response.text
    charts = response.json()
    assert len(charts["daily"]) == 30
    assert (
        charts["summary"]["gross_profit_minor"] == 10000
        and charts["summary"]["net_profit_minor"] == 9000
    )
    assert (
        sum(x["sales_minor"] for x in charts["daily"])
        == charts["summary"]["net_sales_minor"]
        == 25000
    )
    assert (
        sum(x["gross_profit_minor"] for x in charts["daily"])
        == charts["summary"]["gross_profit_minor"]
    )
    assert (
        charts["top_products"][0]["quantity"] == 1
        and charts["top_products"][0]["net_sales_minor"] == 25000
    )
    assert (
        charts["staff"][0]["user_id"] == user["id"]
        and charts["staff"][0]["net_sales_minor"] == 25000
    )
    assert charts["staff"][0]["fulfillment_percent"] == 100
    assert charts["low_stock"][0]["stock"] == 4
    assert c.get("/api/commerce/dashboard-insights?days=14").status_code == 422


def test_dashboard_unknown_cost_unposted_orders_and_tenant_roles(setup):
    c, factory = setup
    first = register(c)
    customer, p = catalog(c)
    order = c.post(
        "/api/orders",
        json=order_body(customer, p),
        headers={"Idempotency-Key": "unposted-chart-key"},
    ).json()
    charts = c.get("/api/commerce/dashboard-insights").json()
    assert (
        charts["summary"]["unposted_orders"] == 1
        and charts["summary"]["net_sales_minor"] == 0
        and charts["top_products"] == []
    )
    assert (
        post(
            c,
            f"/orders/{order['id']}/payments",
            {"amount_minor": 50000},
            "chart-payment-key",
        ).status_code
        == 201
    )
    with factory() as db:
        o = db.get(Order, order["id"])
        o.created_at -= timedelta(days=60)
        db.commit()
    charts = c.get("/api/commerce/dashboard-insights").json()
    assert charts["summary"]["gross_profit_minor"] is None
    assert any(x["gross_profit_minor"] is None for x in charts["daily"])
    assert (
        charts["staff"][0]["order_count"] == 0
        and charts["staff"][0]["fulfillment_percent"] is None
    )
    second = register(c, "chart-second")
    assert c.get("/api/commerce/dashboard-insights").json()["top_products"] == []
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
    assert c.get("/api/commerce/dashboard-insights").status_code == 403
