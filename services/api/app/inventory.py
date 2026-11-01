"""One shared stock ledger for POS, WhatsApp orders, GRNs and transfers."""

from fastapi import HTTPException
from sqlalchemy import select, text

from .models import StockMovement, Warehouse, WarehouseBalance
from .security import scoped


def ensure_main(db, organization_id):
    if db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT set_config('app.organization_id', :org, true)"),
            {"org": organization_id},
        )
    warehouse = db.scalar(
        select(Warehouse).where(
            Warehouse.organization_id == organization_id, Warehouse.code == "MAIN"
        )
    )
    if not warehouse:
        warehouse = Warehouse(
            organization_id=organization_id,
            name="Main warehouse",
            code="MAIN",
            active=True,
        )
        db.add(warehouse)
        db.flush()
    return warehouse


def select_warehouse(db, tenant, warehouse_id=None):
    warehouse = (
        scoped(db, Warehouse, tenant, warehouse_id)
        if warehouse_id
        else ensure_main(db, tenant.id)
    )
    if not warehouse.active:
        raise HTTPException(409, "Choose an active warehouse")
    return warehouse


def available_at(db, product, warehouse):
    balance = db.scalar(
        select(WarehouseBalance).where(
            WarehouseBalance.organization_id == product.organization_id,
            WarehouseBalance.product_id == product.id,
            WarehouseBalance.warehouse_id == warehouse.id,
        )
    )
    if balance:
        return balance.quantity
    # Bootstrap support for existing local fixtures/seed data, never assign an existing allocation twice.
    any_balance = db.scalar(
        select(WarehouseBalance.id)
        .where(
            WarehouseBalance.organization_id == product.organization_id,
            WarehouseBalance.product_id == product.id,
        )
        .limit(1)
    )
    return product.stock if not any_balance and warehouse.code == "MAIN" else 0


def balance_for(db, product, warehouse):
    balances = list(
        db.scalars(
            select(WarehouseBalance)
            .where(
                WarehouseBalance.organization_id == product.organization_id,
                WarehouseBalance.product_id == product.id,
            )
            .with_for_update()
        )
    )
    if not balances:
        main = ensure_main(db, product.organization_id)
        baseline = WarehouseBalance(
            organization_id=product.organization_id,
            warehouse_id=main.id,
            product_id=product.id,
            quantity=product.stock,
        )
        db.add(baseline)
        db.flush()
        balances = [baseline]
    balance = next((row for row in balances if row.warehouse_id == warehouse.id), None)
    if not balance:
        balance = WarehouseBalance(
            organization_id=product.organization_id,
            warehouse_id=warehouse.id,
            product_id=product.id,
            quantity=0,
        )
        db.add(balance)
        db.flush()
    return balance


def move_stock(db, tenant, product, delta, warehouse, reason):
    balance = balance_for(db, product, warehouse)
    if (
        not 0 <= balance.quantity + delta <= 10_000_000
        or not 0 <= product.stock + delta <= 10_000_000
    ):
        raise HTTPException(
            409,
            f"Insufficient stock or stock bounds exceeded for {product.name} in {warehouse.name}",
        )
    balance.quantity += delta
    product.stock += delta
    db.add(
        StockMovement(
            organization_id=tenant.id,
            product_id=product.id,
            warehouse_id=warehouse.id,
            delta=delta,
            reason=reason[:200],
            created_by=tenant.user_id,
        )
    )


def selling_price(product, quantity, price_mode):
    if (
        price_mode == "wholesale"
        and product.wholesale_price_minor is not None
        and quantity >= product.wholesale_min_qty
    ):
        return product.wholesale_price_minor
    return product.price_minor


def order_totals(subtotal, discount, tax_basis_points):
    if discount > subtotal:
        raise HTTPException(422, "Discount cannot exceed the subtotal")
    taxable = subtotal - discount
    tax = (taxable * tax_basis_points + 5000) // 10000
    total = taxable + tax
    if total > 2_000_000_000:
        raise HTTPException(422, "Order total exceeds the supported amount")
    return tax, total
