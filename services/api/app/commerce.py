"""Tenant-scoped sales, purchasing and financial operations (integer minor units)."""

from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .inventory import (
    available_at,
    move_stock,
    order_totals,
    select_warehouse,
    selling_price,
)
from .models import (
    AuditEvent,
    Customer,
    CustomerPayment,
    Expense,
    Membership,
    Order,
    OrderLine,
    Product,
    Purchase,
    SalesReturn,
    StockTransfer,
    Supplier,
    User,
    Warehouse,
    WarehouseBalance,
    as_utc,
    now,
)
from .schemas import OrderInput, OrderItem, StrictModel
from .security import Tenant, digest, lock_org, require, scoped, tenant_context

router = APIRouter(prefix="/api/commerce", tags=["commerce"])
COL = ZoneInfo("Asia/Colombo")
KEY = Header(..., min_length=8, max_length=80)
T = Depends(tenant_context)
D = Depends(get_db)
Money = int


def data(row):
    return {
        c.name: getattr(row, c.name)
        for c in row.__table__.columns
        if c.name
        not in {"request_hash", "idempotency_key", "pos_request_hash", "password_hash"}
    }


def rows(db, model, tenant):
    return list(db.scalars(select(model).where(model.organization_id == tenant.id)))


def audit(db, tenant, action, entity):
    db.add(
        AuditEvent(
            organization_id=tenant.id,
            actor_id=tenant.user_id,
            action=action,
            entity_id=entity,
        )
    )


def fingerprint(body, extra=""):
    return digest(extra + body.model_dump_json())


def replay(db, model, tenant, key, hashed):
    obj = db.scalar(
        select(model).where(
            model.organization_id == tenant.id, model.idempotency_key == key
        )
    )
    if obj and obj.request_hash != hashed:
        raise HTTPException(409, "Idempotency key was used for a different request")
    return obj


def checked_items(db, tenant, items):
    ids = [x.product_id for x in items]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, "Combine duplicate products first")
    result = {
        p.id: p
        for p in db.scalars(
            select(Product)
            .where(Product.organization_id == tenant.id, Product.id.in_(ids))
            .order_by(Product.id)
            .with_for_update()
        )
    }
    if len(result) != len(ids) or any(not p.active for p in result.values()):
        raise HTTPException(422, "A selected product is unavailable")
    return result


class Quote(StrictModel):
    items: list[OrderItem] = Field(min_length=1, max_length=100)
    warehouse_id: str | None = Field(default=None, max_length=36)
    price_mode: Literal["retail", "wholesale"] = "retail"
    discount_minor: int = Field(default=0, ge=0, le=2_000_000_000, strict=True)
    tax_basis_points: int = Field(default=0, ge=0, le=10000, strict=True)


@router.post("/quote")
def quote(body: Quote, tenant: Tenant = T, db: Session = D):
    warehouse = select_warehouse(db, tenant, body.warehouse_id)
    products = checked_items(db, tenant, body.items)
    result = []
    for item in body.items:
        p = products[item.product_id]
        if item.quantity < p.min_order_qty:
            raise HTTPException(
                422, f"Minimum quantity for {p.name} is {p.min_order_qty}"
            )
        price = selling_price(p, item.quantity, body.price_mode)
        result.append(
            {
                "product_id": p.id,
                "name": p.name,
                "quantity": item.quantity,
                "price_minor": price,
                "available": available_at(db, p, warehouse) if p.track_stock else None,
            }
        )
    subtotal = sum(x["quantity"] * x["price_minor"] for x in result)
    tax, total = order_totals(subtotal, body.discount_minor, body.tax_basis_points)
    return {
        "items": result,
        "subtotal_minor": subtotal,
        "discount_minor": body.discount_minor,
        "tax_minor": tax,
        "total_minor": total,
        "warehouse_id": warehouse.id,
    }


def ledger(db, tenant):
    returned, paid = {}, {}
    for row in rows(db, SalesReturn, tenant):
        returned[row.order_id] = returned.get(row.order_id, 0) + row.total_minor
    for row in rows(db, CustomerPayment, tenant):
        paid[row.order_id] = paid.get(row.order_id, 0) + (
            row.amount_minor if row.kind == "payment" else -row.amount_minor
        )
    return returned, paid


def balances(db, tenant):
    returned, paid = ledger(db, tenant)
    return {
        o.id: max(o.total_minor - returned.get(o.id, 0) - paid.get(o.id, 0), 0)
        for o in rows(db, Order, tenant)
        if o.financial_posted and o.status != "cancelled"
    }


def enforce_credit(db, tenant, order, customer, new_due):
    if new_due > 0 and customer.walk_in:
        raise HTTPException(409, "Choose a named trade customer for credit sales")
    existing = balances(db, tenant)
    outstanding = sum(
        existing.get(o.id, 0)
        for o in rows(db, Order, tenant)
        if o.customer_id == customer.id and o.id != order.id
    )
    if new_due > 0 and outstanding + new_due > customer.credit_limit_minor:
        raise HTTPException(
            409,
            "Customer credit limit exceeded; record payment or update the approved credit limit",
        )


def post_financial(order, customer):
    if not order.financial_posted:
        order.financial_posted = True
        order.posted_at = now()
        order.due_date = datetime.now(COL).date() + timedelta(
            days=customer.payment_terms_days
        )


class Sale(Quote):
    customer_id: str | None = Field(default=None, max_length=36)
    human_confirmed: Literal[True]
    expected_total_minor: int = Field(ge=0, le=2_000_000_000, strict=True)
    paid_minor: int = Field(ge=0, le=2_000_000_000, strict=True)
    payment_method: Literal["cash", "card", "bank_transfer", "credit"] = "cash"
    reference: str = Field(default="", max_length=120)

    @field_validator("human_confirmed", mode="before")
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError("Explicit human confirmation is required")
        return value


@router.post("/sales", status_code=201)
def sale(body: Sale, idempotency_key: str = KEY, tenant: Tenant = T, db: Session = D):
    from .main import confirm_order, order_result

    require(tenant, "owner", "admin", "staff")
    lock_org(db, tenant)
    hashed = fingerprint(body)
    existing = db.scalar(
        select(Order).where(
            Order.organization_id == tenant.id, Order.idempotency_key == idempotency_key
        )
    )
    if existing:
        if existing.pos_request_hash != hashed:
            raise HTTPException(409, "Idempotency key was used for a different sale")
        return order_result(db, tenant, existing)
    if body.payment_method == "credit" and body.paid_minor:
        raise HTTPException(422, "Credit-only sales cannot include a paid amount")
    if body.customer_id:
        customer = scoped(db, Customer, tenant, body.customer_id)
    else:
        customer = db.scalar(
            select(Customer).where(
                Customer.organization_id == tenant.id, Customer.walk_in.is_(True)
            )
        )
        if not customer:
            customer = Customer(
                organization_id=tenant.id, name="Walk-in customer", walk_in=True
            )
            db.add(customer)
            db.flush()
    order_body = OrderInput(
        **body.model_dump(
            exclude={"customer_id", "paid_minor", "payment_method", "reference"}
        ),
        customer_id=customer.id,
    )
    result = confirm_order(order_body, idempotency_key, tenant, db)
    order = scoped(db, Order, tenant, result["id"])
    if body.paid_minor > order.total_minor:
        raise HTTPException(
            422, "Record only the invoice amount paid; return cash change separately"
        )
    enforce_credit(db, tenant, order, customer, order.total_minor - body.paid_minor)
    post_financial(order, customer)
    order.source, order.pos_request_hash, order.status = "pos", hashed, "fulfilled"
    if body.paid_minor:
        db.add(
            CustomerPayment(
                organization_id=tenant.id,
                order_id=order.id,
                customer_id=customer.id,
                amount_minor=body.paid_minor,
                method=body.payment_method,
                reference=body.reference,
                idempotency_key="sale:" + order.id,
                request_hash=hashed,
                created_by=tenant.user_id,
            )
        )
    audit(db, tenant, "sale.posted", order.id)
    db.commit()
    return order_result(db, tenant, order)


class PaymentInput(StrictModel):
    amount_minor: int = Field(ge=0, le=2_000_000_000, strict=True)
    method: Literal["cash", "card", "bank_transfer", "credit"] = "cash"
    reference: str = Field(default="", max_length=120)


@router.post("/orders/{order_id}/payments", status_code=201)
def payment(
    order_id: str,
    body: PaymentInput,
    idempotency_key: str = KEY,
    tenant: Tenant = T,
    db: Session = D,
):
    require(tenant, "owner", "admin", "staff")
    lock_org(db, tenant)
    hashed = fingerprint(body, order_id)
    old = replay(db, CustomerPayment, tenant, idempotency_key, hashed)
    if old:
        return data(old)
    order = scoped(db, Order, tenant, order_id)
    if order.status == "cancelled":
        raise HTTPException(409, "Cancelled orders cannot receive payments")
    customer = scoped(db, Customer, tenant, order.customer_id)
    returned, paid = ledger(db, tenant)
    due = order.total_minor - returned.get(order.id, 0) - paid.get(order.id, 0)
    if body.amount_minor > due or (body.method == "credit" and body.amount_minor):
        raise HTTPException(
            422, "Payment exceeds the remaining amount or uses an invalid method"
        )
    enforce_credit(db, tenant, order, customer, due - body.amount_minor)
    post_financial(order, customer)
    if body.amount_minor:
        obj = CustomerPayment(
            organization_id=tenant.id,
            order_id=order.id,
            customer_id=customer.id,
            amount_minor=body.amount_minor,
            method=body.method,
            reference=body.reference,
            idempotency_key=idempotency_key,
            request_hash=hashed,
            created_by=tenant.user_id,
        )
        db.add(obj)
        db.flush()
        result = data(obj)
    else:
        result = {"posted": True, "outstanding_minor": due}
    audit(db, tenant, "payment.recorded", order.id)
    db.commit()
    return result


@router.get("/accounts")
def accounts(tenant: Tenant = T, db: Session = D):
    require(tenant, "owner", "admin", "staff")
    amounts = balances(db, tenant)
    returned, paid = ledger(db, tenant)
    orders = rows(db, Order, tenant)
    today = datetime.now(COL).date()
    return [
        {
            **data(c),
            "outstanding_minor": sum(
                amounts.get(o.id, 0) for o in orders if o.customer_id == c.id
            ),
            "overdue_minor": sum(
                amounts.get(o.id, 0)
                for o in orders
                if o.customer_id == c.id and o.due_date and o.due_date < today
            ),
            "orders": [
                {
                    **data(o),
                    "outstanding_minor": amounts.get(o.id, 0)
                    if o.financial_posted
                    else None,
                    "refund_due_minor": max(
                        paid.get(o.id, 0) - (o.total_minor - returned.get(o.id, 0)), 0
                    ),
                    "days_overdue": max((today - o.due_date).days, 0)
                    if o.due_date
                    else 0,
                }
                for o in orders
                if o.customer_id == c.id
            ],
        }
        for c in rows(db, Customer, tenant)
    ]


@router.get("/orders/{order_id}/ledger")
def order_ledger(order_id: str, tenant: Tenant = T, db: Session = D):
    scoped(db, Order, tenant, order_id)
    return {
        "payments": [
            data(x) for x in rows(db, CustomerPayment, tenant) if x.order_id == order_id
        ],
        "returns": [
            data(x) for x in rows(db, SalesReturn, tenant) if x.order_id == order_id
        ],
    }


class SupplierInput(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(default="", max_length=40)
    address: str = Field(default="", max_length=500)
    active: bool = True


@router.get("/suppliers")
def suppliers(tenant: Tenant = T, db: Session = D):
    require(tenant, "owner", "admin", "staff")
    return [data(x) for x in rows(db, Supplier, tenant)]


@router.post("/suppliers", status_code=201)
def supplier_create(body: SupplierInput, tenant: Tenant = T, db: Session = D):
    require(tenant, "owner", "admin")
    obj = Supplier(organization_id=tenant.id, **body.model_dump())
    db.add(obj)
    db.flush()
    audit(db, tenant, "supplier.created", obj.id)
    db.commit()
    return data(obj)


@router.put("/suppliers/{supplier_id}")
def supplier_update(
    supplier_id: str, body: SupplierInput, tenant: Tenant = T, db: Session = D
):
    require(tenant, "owner", "admin")
    obj = scoped(db, Supplier, tenant, supplier_id)
    for k, v in body.model_dump().items():
        setattr(obj, k, v)
    audit(db, tenant, "supplier.updated", obj.id)
    db.commit()
    return data(obj)


class WarehouseInput(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Z0-9_-]+$")


@router.get("/warehouses")
def warehouses(tenant: Tenant = T, db: Session = D):
    return [data(x) for x in rows(db, Warehouse, tenant)]


@router.post("/warehouses", status_code=201)
def warehouse_create(body: WarehouseInput, tenant: Tenant = T, db: Session = D):
    require(tenant, "owner", "admin")
    lock_org(db, tenant)
    if any(x.code == body.code for x in rows(db, Warehouse, tenant)):
        raise HTTPException(409, "Warehouse code already exists")
    obj = Warehouse(organization_id=tenant.id, **body.model_dump())
    db.add(obj)
    db.flush()
    audit(db, tenant, "warehouse.created", obj.id)
    db.commit()
    return data(obj)


@router.get("/stock")
def warehouse_stock(warehouse_id: str, tenant: Tenant = T, db: Session = D):
    warehouse = select_warehouse(db, tenant, warehouse_id)
    allocations = {
        x.product_id: x.quantity
        for x in db.scalars(
            select(WarehouseBalance).where(
                WarehouseBalance.organization_id == tenant.id,
                WarehouseBalance.warehouse_id == warehouse.id,
            )
        )
    }
    allocated = set(
        db.scalars(
            select(WarehouseBalance.product_id).where(
                WarehouseBalance.organization_id == tenant.id
            )
        )
    )
    return [
        {
            "product_id": p.id,
            "name": p.name,
            "sku": p.sku,
            "quantity": allocations.get(
                p.id,
                p.stock if p.id not in allocated and warehouse.code == "MAIN" else 0,
            ),
        }
        for p in rows(db, Product, tenant)
        if p.track_stock
    ]


class TransferInput(StrictModel):
    product_id: str = Field(min_length=1, max_length=36)
    from_warehouse_id: str = Field(min_length=1, max_length=36)
    to_warehouse_id: str = Field(min_length=1, max_length=36)
    quantity: int = Field(gt=0, le=1_000_000, strict=True)


@router.post("/transfers", status_code=201)
def transfer(
    body: TransferInput, idempotency_key: str = KEY, tenant: Tenant = T, db: Session = D
):
    require(tenant, "owner", "admin")
    lock_org(db, tenant)
    hashed = fingerprint(body)
    old = replay(db, StockTransfer, tenant, idempotency_key, hashed)
    if old:
        return data(old)
    if body.from_warehouse_id == body.to_warehouse_id:
        raise HTTPException(422, "Choose two different warehouses")
    product = scoped(db, Product, tenant, body.product_id)
    if not product.track_stock:
        raise HTTPException(422, "Service products cannot be transferred")
    source, target = (
        select_warehouse(db, tenant, body.from_warehouse_id),
        select_warehouse(db, tenant, body.to_warehouse_id),
    )
    move_stock(db, tenant, product, -body.quantity, source, "Warehouse transfer out")
    db.flush()
    move_stock(db, tenant, product, body.quantity, target, "Warehouse transfer in")
    obj = StockTransfer(
        organization_id=tenant.id,
        **body.model_dump(),
        idempotency_key=idempotency_key,
        request_hash=hashed,
        created_by=tenant.user_id,
    )
    db.add(obj)
    db.flush()
    audit(db, tenant, "stock.transferred", obj.id)
    db.commit()
    return data(obj)


class PurchaseLine(OrderItem):
    cost_minor: int = Field(ge=0, le=100_000_000, strict=True)


class PurchaseInput(StrictModel):
    supplier_id: str = Field(min_length=1, max_length=36)
    warehouse_id: str | None = Field(default=None, max_length=36)
    reference: str = Field(default="", max_length=100)
    items: list[PurchaseLine] = Field(min_length=1, max_length=100)


@router.get("/purchases")
def purchases(tenant: Tenant = T, db: Session = D):
    require(tenant, "owner", "admin", "staff")
    return [data(x) for x in rows(db, Purchase, tenant)]


@router.post("/purchases", status_code=201)
def purchase_create(
    body: PurchaseInput, idempotency_key: str = KEY, tenant: Tenant = T, db: Session = D
):
    require(tenant, "owner", "admin")
    lock_org(db, tenant)
    hashed = fingerprint(body)
    old = replay(db, Purchase, tenant, idempotency_key, hashed)
    if old:
        return data(old)
    supplier = scoped(db, Supplier, tenant, body.supplier_id)
    if not supplier.active:
        raise HTTPException(422, "Supplier is archived")
    warehouse = select_warehouse(db, tenant, body.warehouse_id)
    products = checked_items(db, tenant, body.items)
    if any(not x.track_stock for x in products.values()):
        raise HTTPException(422, "Purchases require stock products")
    total = sum(x.quantity * x.cost_minor for x in body.items)
    if total > 2_000_000_000:
        raise HTTPException(422, "Purchase total exceeds the supported amount")
    obj = Purchase(
        organization_id=tenant.id,
        supplier_id=supplier.id,
        warehouse_id=warehouse.id,
        reference=body.reference,
        lines=[
            {**x.model_dump(), "name": products[x.product_id].name} for x in body.items
        ],
        total_minor=total,
        idempotency_key=idempotency_key,
        request_hash=hashed,
        created_by=tenant.user_id,
    )
    db.add(obj)
    db.flush()
    audit(db, tenant, "purchase.created", obj.id)
    db.commit()
    return data(obj)


class PurchaseState(StrictModel):
    status: Literal["received", "cancelled"]


@router.patch("/purchases/{purchase_id}")
def purchase_receive(
    purchase_id: str, body: PurchaseState, tenant: Tenant = T, db: Session = D
):
    require(tenant, "owner", "admin")
    lock_org(db, tenant)
    obj = scoped(db, Purchase, tenant, purchase_id)
    if obj.status == body.status:
        return data(obj)
    if obj.status != "draft":
        raise HTTPException(409, "Purchase is already closed")
    if body.status == "received":
        warehouse = select_warehouse(db, tenant, obj.warehouse_id)
        for line in sorted(obj.lines, key=lambda x: x["product_id"]):
            product = scoped(db, Product, tenant, line["product_id"])
            before = product.stock
            if before == 0:
                product.cost_minor = line["cost_minor"]
            elif product.cost_minor is not None:
                product.cost_minor = (
                    before * product.cost_minor
                    + line["quantity"] * line["cost_minor"]
                    + (before + line["quantity"]) // 2
                ) // (before + line["quantity"])
            move_stock(
                db, tenant, product, line["quantity"], warehouse, f"GRN {obj.id}"
            )
        obj.received_at = now()
    obj.status = body.status
    audit(db, tenant, "purchase." + body.status, obj.id)
    db.commit()
    return data(obj)


class ReturnLine(OrderItem):
    resellable: bool = True


class ReturnInput(StrictModel):
    items: list[ReturnLine] = Field(min_length=1, max_length=100)
    warehouse_id: str | None = Field(default=None, max_length=36)
    reason: str = Field(min_length=3, max_length=500)
    refund_minor: int = Field(default=0, ge=0, le=2_000_000_000, strict=True)
    method: Literal["cash", "card", "bank_transfer"] = "cash"


@router.post("/orders/{order_id}/returns", status_code=201)
def sales_return(
    order_id: str,
    body: ReturnInput,
    idempotency_key: str = KEY,
    tenant: Tenant = T,
    db: Session = D,
):
    require(tenant, "owner", "admin")
    lock_org(db, tenant)
    hashed = fingerprint(body, order_id)
    old = replay(db, SalesReturn, tenant, idempotency_key, hashed)
    if old:
        return data(old)
    order = scoped(db, Order, tenant, order_id)
    if order.status == "cancelled":
        raise HTTPException(409, "Cancelled order stock has already been restored")
    warehouse = select_warehouse(db, tenant, body.warehouse_id or order.warehouse_id)
    lines = {
        x.product_id: x
        for x in db.scalars(
            select(OrderLine).where(
                OrderLine.organization_id == tenant.id, OrderLine.order_id == order.id
            )
        )
    }
    previous = [x for x in rows(db, SalesReturn, tenant) if x.order_id == order.id]
    quantities = {}
    for r in previous:
        for line in r.lines:
            quantities[line["product_id"]] = (
                quantities.get(line["product_id"], 0) + line["quantity"]
            )
    if len({x.product_id for x in body.items}) != len(body.items):
        raise HTTPException(422, "Combine duplicate return lines")
    result = []
    for item in body.items:
        line = lines.get(item.product_id)
        if (
            not line
            or quantities.get(item.product_id, 0) + item.quantity > line.quantity
        ):
            raise HTTPException(422, "Return quantity exceeds the quantity sold")
        result.append(
            {
                **item.model_dump(),
                "price_minor": line.price_minor,
                "cost_minor": line.cost_minor,
                "track_stock": line.track_stock,
            }
        )
        quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity
        if item.resellable and line.track_stock:
            product = scoped(db, Product, tenant, item.product_id)
            move_stock(
                db,
                tenant,
                product,
                item.quantity,
                warehouse,
                f"Sales return {order.id}",
            )
    subtotal = sum(x.quantity * x.price_minor for x in lines.values())
    gross_returned = sum(
        quantities.get(x.product_id, 0) * x.price_minor for x in lines.values()
    )
    cumulative_credit = (
        order.total_minor * gross_returned // subtotal if subtotal else 0
    )
    cumulative_tax = (
        cumulative_credit * order.tax_minor // order.total_minor
        if order.total_minor
        else 0
    )
    returned_tax = cumulative_tax - sum(x.tax_minor for x in previous)
    credit = cumulative_credit - sum(x.total_minor for x in previous)
    _, paid = ledger(db, tenant)
    max_refund = max(paid.get(order.id, 0) - (order.total_minor - cumulative_credit), 0)
    if body.refund_minor > max_refund:
        raise HTTPException(
            422, "Refund exceeds the amount paid above the remaining invoice value"
        )
    obj = SalesReturn(
        organization_id=tenant.id,
        order_id=order.id,
        warehouse_id=warehouse.id,
        lines=result,
        total_minor=credit,
        tax_minor=returned_tax,
        reason=body.reason,
        idempotency_key=idempotency_key,
        request_hash=hashed,
        created_by=tenant.user_id,
    )
    db.add(obj)
    db.flush()
    if body.refund_minor:
        db.add(
            CustomerPayment(
                organization_id=tenant.id,
                order_id=order.id,
                customer_id=order.customer_id,
                amount_minor=body.refund_minor,
                kind="refund",
                method=body.method,
                reference="Return " + obj.id,
                idempotency_key="return:" + obj.id,
                request_hash=hashed,
                created_by=tenant.user_id,
            )
        )
    audit(db, tenant, "sale.returned", obj.id)
    db.commit()
    return data(obj)


class ExpenseInput(StrictModel):
    category: str = Field(min_length=1, max_length=60)
    description: str = Field(min_length=3, max_length=500)
    amount_minor: int = Field(gt=0, le=2_000_000_000, strict=True)
    paid_on: date
    reference: str = Field(default="", max_length=120)


@router.get("/expenses")
def expenses(tenant: Tenant = T, db: Session = D):
    require(tenant, "owner", "admin")
    return [data(x) for x in rows(db, Expense, tenant)]


@router.post("/expenses", status_code=201)
def expense_create(
    body: ExpenseInput, idempotency_key: str = KEY, tenant: Tenant = T, db: Session = D
):
    require(tenant, "owner", "admin")
    lock_org(db, tenant)
    hashed = fingerprint(body)
    old = replay(db, Expense, tenant, idempotency_key, hashed)
    if old:
        return data(old)
    obj = Expense(
        organization_id=tenant.id,
        **body.model_dump(),
        idempotency_key=idempotency_key,
        request_hash=hashed,
        created_by=tenant.user_id,
    )
    db.add(obj)
    db.flush()
    audit(db, tenant, "expense.recorded", obj.id)
    db.commit()
    return data(obj)


@router.delete("/expenses/{expense_id}")
def expense_void(expense_id: str, tenant: Tenant = T, db: Session = D):
    require(tenant, "owner", "admin")
    lock_org(db, tenant)
    obj = scoped(db, Expense, tenant, expense_id)
    obj.voided = True
    audit(db, tenant, "expense.voided", obj.id)
    db.commit()
    return data(obj)


@router.get("/reports")
def reports(
    start: date = Query(...),
    end: date = Query(...),
    tenant: Tenant = T,
    db: Session = D,
):
    require(tenant, "owner", "admin")
    if end < start or (end - start).days > 366:
        raise HTTPException(422, "Choose a report period of up to 366 days")
    a, b = (
        datetime.combine(start, time.min, COL).astimezone(timezone.utc),
        datetime.combine(end + timedelta(days=1), time.min, COL).astimezone(
            timezone.utc
        ),
    )

    def during(value):
        return value is not None and a <= as_utc(value) < b

    posted = [
        x
        for x in rows(db, Order, tenant)
        if x.financial_posted and x.status != "cancelled"
    ]
    sales = [x for x in posted if during(x.posted_at)]
    posted_ids, sale_ids = {x.id for x in posted}, {x.id for x in sales}
    returns = [
        x
        for x in rows(db, SalesReturn, tenant)
        if x.order_id in posted_ids and during(x.created_at)
    ]
    lines = [x for x in rows(db, OrderLine, tenant) if x.order_id in sale_ids]
    unknown = sum(x.cost_minor is None for x in lines) + sum(
        x["cost_minor"] is None
        for r in returns
        for x in r.lines
        if x["resellable"] and x["track_stock"]
    )
    cogs = sum(x.quantity * (x.cost_minor or 0) for x in lines) - sum(
        x["quantity"] * (x["cost_minor"] or 0)
        for r in returns
        for x in r.lines
        if x["resellable"] and x["track_stock"]
    )
    # Tax is a liability, excluded from sales/profit; return tax is prorated from its invoice.
    refund_net = sum(r.total_minor - r.tax_minor for r in returns)
    net = sum(x.total_minor - x.tax_minor for x in sales) - refund_net
    expense = sum(
        x.amount_minor
        for x in rows(db, Expense, tenant)
        if not x.voided and start <= x.paid_on <= end
    )
    payments = [x for x in rows(db, CustomerPayment, tenant) if during(x.created_at)]
    return {
        "start": start,
        "end": end,
        "sales_count": len(sales),
        "gross_invoices_minor": sum(x.total_minor for x in sales),
        "returns_minor": sum(x.total_minor for x in returns),
        "net_sales_minor": net,
        "cost_of_sales_minor": None if unknown else cogs,
        "missing_cost_lines": unknown,
        "expenses_minor": expense,
        "gross_profit_minor": None if unknown else net - cogs,
        "net_profit_minor": None if unknown else net - cogs - expense,
        "payments_received_minor": sum(
            x.amount_minor for x in payments if x.kind == "payment"
        ),
        "refunds_paid_minor": sum(
            x.amount_minor for x in payments if x.kind == "refund"
        ),
        "outstanding_minor": sum(balances(db, tenant).values()),
        "unposted_orders": sum(
            not x.financial_posted and x.status != "cancelled"
            for x in rows(db, Order, tenant)
        ),
        "by_warehouse": [
            {
                "warehouse_id": w.id,
                "name": w.name,
                "sales_count": sum(x.warehouse_id == w.id for x in sales),
                "invoices_minor": sum(
                    x.total_minor for x in sales if x.warehouse_id == w.id
                ),
            }
            for w in rows(db, Warehouse, tenant)
        ],
    }


class DeliveryInput(StrictModel):
    status: Literal["pending", "dispatched", "delivered", "failed"]
    assigned_to: str | None = Field(default=None, max_length=36)
    reference: str = Field(default="", max_length=160)


@router.put("/orders/{order_id}/delivery")
def delivery(order_id: str, body: DeliveryInput, tenant: Tenant = T, db: Session = D):
    require(tenant, "owner", "admin", "staff")
    lock_org(db, tenant)
    order = scoped(db, Order, tenant, order_id)
    if order.status == "cancelled":
        raise HTTPException(409, "Order is cancelled")
    if body.assigned_to and not db.get(Membership, (body.assigned_to, tenant.id)):
        raise HTTPException(422, "Assign a member of this workspace")
    order.delivery_status, order.assigned_to, order.delivery_reference = (
        body.status,
        body.assigned_to,
        body.reference,
    )
    if body.status == "delivered":
        order.status = "fulfilled"
    audit(db, tenant, "delivery." + body.status, order.id)
    db.commit()
    return data(order)


@router.get("/team")
def team(tenant: Tenant = T, db: Session = D):
    require(tenant, "owner", "admin", "staff")
    return [
        {
            "user_id": m.user_id,
            "name": u.name,
            "email": u.email if tenant.role in {"owner", "admin"} else "",
            "role": m.role,
        }
        for m, u in db.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.organization_id == tenant.id)
        )
    ]


class MemberInput(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    role: Literal["admin", "staff", "viewer"]


@router.put("/team")
def member_add(body: MemberInput, tenant: Tenant = T, db: Session = D):
    require(tenant, "owner")
    lock_org(db, tenant)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user:
        raise HTTPException(
            422, "Ask this person to register first, then add their email"
        )
    membership = db.get(Membership, (user.id, tenant.id))
    if membership and membership.role == "owner":
        raise HTTPException(409, "The owner role cannot be changed here")
    if membership:
        membership.role = body.role
    else:
        db.add(Membership(user_id=user.id, organization_id=tenant.id, role=body.role))
    audit(db, tenant, "team.role_updated", user.id)
    db.commit()
    return {"user_id": user.id, "role": body.role}


@router.delete("/team/{user_id}")
def member_remove(user_id: str, tenant: Tenant = T, db: Session = D):
    require(tenant, "owner")
    lock_org(db, tenant)
    m = db.get(Membership, (user_id, tenant.id))
    if not m:
        raise HTTPException(404, "Member not found")
    if m.role == "owner":
        raise HTTPException(409, "The owner cannot be removed")
    db.delete(m)
    audit(db, tenant, "team.removed", user_id)
    db.commit()
    return {"removed": True}


class RefundInput(StrictModel):
    amount_minor: int = Field(gt=0, le=2_000_000_000, strict=True)
    method: Literal["cash", "card", "bank_transfer"] = "cash"
    reference: str = Field(default="", max_length=120)


@router.post("/orders/{order_id}/refunds", status_code=201)
def refund_balance(
    order_id: str,
    body: RefundInput,
    idempotency_key: str = KEY,
    tenant: Tenant = T,
    db: Session = D,
):
    require(tenant, "owner", "admin")
    lock_org(db, tenant)
    hashed = fingerprint(body, "refund:" + order_id)
    old = replay(db, CustomerPayment, tenant, idempotency_key, hashed)
    if old:
        return data(old)
    order = scoped(db, Order, tenant, order_id)
    returned, paid = ledger(db, tenant)
    due = max(
        paid.get(order.id, 0) - (order.total_minor - returned.get(order.id, 0)), 0
    )
    if body.amount_minor > due:
        raise HTTPException(
            422, "Refund exceeds the credit balance remaining from returns"
        )
    obj = CustomerPayment(
        organization_id=tenant.id,
        order_id=order.id,
        customer_id=order.customer_id,
        amount_minor=body.amount_minor,
        kind="refund",
        method=body.method,
        reference=body.reference,
        idempotency_key=idempotency_key,
        request_hash=hashed,
        created_by=tenant.user_id,
    )
    db.add(obj)
    db.flush()
    audit(db, tenant, "refund.recorded", obj.id)
    db.commit()
    return data(obj)


@router.get("/orders/{order_id}/receipt")
def receipt(order_id: str, tenant: Tenant = T, db: Session = D):
    from fastapi import Response

    from .invoices import invoice_pdf
    from .models import Organization

    order = scoped(db, Order, tenant, order_id)
    if not order.financial_posted:
        raise HTTPException(
            409, "Record payment or credit before creating a payment record"
        )
    lines = list(
        db.scalars(
            select(OrderLine).where(
                OrderLine.organization_id == tenant.id, OrderLine.order_id == order.id
            )
        )
    )
    payments = [x for x in rows(db, CustomerPayment, tenant) if x.order_id == order.id]
    returned = sum(
        x.total_minor for x in rows(db, SalesReturn, tenant) if x.order_id == order.id
    )
    try:
        content = invoice_pdf(
            order,
            lines,
            db.get(Organization, tenant.id),
            payments=payments,
            returned=returned,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return Response(
        content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="payment-record-{order.id}.pdf"'
        },
    )
