"""Read-only dashboard charts from posted financial records and current inventory."""

from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from .commerce import COL, D, T, reports, rows
from .models import Order, OrderLine, Product, SalesReturn, User, as_utc
from .security import require

router = APIRouter(prefix="/api/commerce")


def allocate(amount, weights):
    """Deterministic integer allocation; the last line absorbs rounding cents."""
    total = sum(weights)
    if not total:
        return [0] * len(weights)
    result = [amount * weight // total for weight in weights]
    if result:
        result[-1] += amount - sum(result)
    return result


@router.get("/dashboard-insights")
def dashboard_insights(days: int = Query(30, ge=7, le=90), tenant=T, db=D):
    require(tenant, "owner", "admin")
    if days not in (7, 30, 90):
        raise HTTPException(422, "Choose 7, 30 or 90 days")
    end = datetime.now(COL).date()
    start = end - timedelta(days=days - 1)
    summary = reports(start=start, end=end, tenant=tenant, db=db)
    daily = {
        (start + timedelta(days=i)).isoformat(): {
            "sales_minor": 0,
            "cost_minor": 0,
            "missing_cost_lines": 0,
        }
        for i in range(days)
    }
    orders = {o.id: o for o in rows(db, Order, tenant) if o.status != "cancelled"}
    lines = defaultdict(list)
    for line in db.scalars(
        select(OrderLine).where(
            OrderLine.organization_id == tenant.id, OrderLine.order_id.in_(orders)
        )
    ):
        lines[line.order_id].append(line)
    products, staff = {}, {}

    def date_key(value):
        return as_utc(value).astimezone(COL).date().isoformat() if value else ""

    def worker(user_id):
        return staff.setdefault(
            user_id,
            {
                "user_id": user_id,
                "order_count": 0,
                "fulfilled_orders": 0,
                "net_sales_minor": 0,
            },
        )

    def product(line):
        return products.setdefault(
            line.product_id,
            {
                "product_id": line.product_id,
                "name": line.product_name,
                "quantity": 0,
                "net_sales_minor": 0,
            },
        )

    for order in orders.values():
        if date_key(order.created_at) in daily:
            member = worker(order.created_by)
            member["order_count"] += 1
            member["fulfilled_orders"] += int(order.status == "fulfilled")
        day = date_key(order.posted_at)
        if not order.financial_posted or day not in daily:
            continue
        net = order.total_minor - order.tax_minor
        daily[day]["sales_minor"] += net
        worker(order.created_by)["net_sales_minor"] += net
        order_lines = sorted(lines[order.id], key=lambda x: x.id)
        revenue = allocate(
            net, [line.price_minor * line.quantity for line in order_lines]
        )
        for line, value in zip(order_lines, revenue, strict=True):
            item = product(line)
            item["quantity"] += line.quantity
            item["net_sales_minor"] += value
            if line.cost_minor is None:
                daily[day]["missing_cost_lines"] += 1
            else:
                daily[day]["cost_minor"] += line.quantity * line.cost_minor

    for returned in rows(db, SalesReturn, tenant):
        order = orders.get(returned.order_id)
        day = date_key(returned.created_at)
        if not order or not order.financial_posted or day not in daily:
            continue
        credit = returned.total_minor - returned.tax_minor
        daily[day]["sales_minor"] -= credit
        worker(order.created_by)["net_sales_minor"] -= credit
        revenue = allocate(
            credit, [line["price_minor"] * line["quantity"] for line in returned.lines]
        )
        for line, value in zip(returned.lines, revenue, strict=True):
            original = next(
                (x for x in lines[order.id] if x.product_id == line["product_id"]), None
            )
            if original:
                item = product(original)
                item["quantity"] -= line["quantity"]
                item["net_sales_minor"] -= value
            if line["resellable"] and line["track_stock"]:
                if line["cost_minor"] is None:
                    daily[day]["missing_cost_lines"] += 1
                else:
                    daily[day]["cost_minor"] -= line["quantity"] * line["cost_minor"]

    names = {u.id: u.name for u in db.scalars(select(User).where(User.id.in_(staff)))}
    for member in staff.values():
        member["name"] = names.get(member["user_id"], "Former workspace member")
        member["fulfillment_percent"] = (
            round(member["fulfilled_orders"] * 100 / member["order_count"], 1)
            if member["order_count"]
            else None
        )
    low_stock = list(
        db.scalars(
            select(Product)
            .where(
                Product.organization_id == tenant.id,
                Product.active.is_(True),
                Product.track_stock.is_(True),
                Product.stock <= Product.reorder_level,
            )
            .order_by(Product.stock, Product.name)
        )
    )
    return {
        "period": {"start": start, "end": end, "days": days},
        "summary": {
            k: summary[k]
            for k in (
                "net_sales_minor",
                "cost_of_sales_minor",
                "gross_profit_minor",
                "expenses_minor",
                "net_profit_minor",
                "sales_count",
                "missing_cost_lines",
                "unposted_orders",
            )
        },
        "daily": [
            {
                "date": day,
                "sales_minor": values["sales_minor"],
                "gross_profit_minor": None
                if values["missing_cost_lines"]
                else values["sales_minor"] - values["cost_minor"],
            }
            for day, values in daily.items()
        ],
        "low_stock_count": len(low_stock),
        "low_stock": [
            {
                "id": p.id,
                "name": p.name,
                "sku": p.sku,
                "stock": p.stock,
                "unit": p.unit,
                "reorder_level": p.reorder_level,
            }
            for p in low_stock[:8]
        ],
        "top_products": sorted(
            (p for p in products.values() if p["quantity"] > 0),
            key=lambda x: (-x["quantity"], -x["net_sales_minor"], x["name"]),
        )[:6],
        "staff": sorted(
            staff.values(),
            key=lambda x: (-x["net_sales_minor"], -x["fulfilled_orders"], x["name"]),
        )[:8],
    }
