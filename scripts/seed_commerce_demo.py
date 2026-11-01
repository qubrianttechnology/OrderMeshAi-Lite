"""Create an isolated local demo; never attach a WhatsApp number or alter real workspaces."""

import json
import secrets
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))
from app.config import settings
from app.db import SessionLocal, is_sqlite
from app.inventory import ensure_main, move_stock
from app.models import Customer, Membership, Organization, Product, Supplier, User, now
from app.security import Tenant, passwords
from sqlalchemy import select, text


def main():
    if settings.app_env != "development" or not is_sqlite:
        raise SystemExit(
            "Demo seed is restricted to the local SQLite development database."
        )
    access = ROOT / ".local" / "demo-access.json"
    with SessionLocal() as db:
        version = db.execute(
            text("select version_num from alembic_version")
        ).scalar_one()
        if version != "0015":
            raise SystemExit(
                "Upgrade local migrations to 0015 before creating the demo."
            )
        email = "demo-wholesale@ordermesh.example"
        user = db.scalar(select(User).where(User.email == email))
        if user:
            membership = db.scalar(
                select(Membership)
                .join(Organization, Organization.id == Membership.organization_id)
                .where(
                    Membership.user_id == user.id,
                    Organization.name == "OrderMesh Demo Wholesale",
                )
            )
            org = (
                db.get(Organization, membership.organization_id) if membership else None
            )
            if (
                not org
                or org.business_profile.get("demo_workspace") != "true"
                or not access.exists()
            ):
                raise SystemExit(
                    "Existing demo identity does not match its local access record; no data changed."
                )
            password = json.loads(access.read_text(encoding="utf-8"))["password"]
        else:
            password = secrets.token_urlsafe(24)
            user = User(
                email=email, name="Demo owner", password_hash=passwords.hash(password)
            )
            org = Organization(
                name="OrderMesh Demo Wholesale",
                business_type="wholesale",
                monthly_order_limit=500,
                trial_ends_at=now() + timedelta(days=15),
                business_profile={
                    "demo_workspace": "true",
                    "description": "DEMO ONLY. Wholesale groceries, electronics, vehicle parts and general trade supplies.",
                    "offerings": "Rice 1kg, Sugar 1kg, Milk Powder; synthetic products across nine wholesale categories.",
                    "customers": "Retail stores and wholesale trade buyers. All products, costs, prices and customers are examples.",
                    "business_examples": "Rice 1kg 2; Sugar 1kg 1; quotation for trade supplies",
                    "personal_examples": "Family conversations and personal plans are private messages.",
                    "spam_examples": "Unsolicited prize offers, promotions and suspicious links.",
                    "hours": "Monday to Saturday 09:00-18:00",
                    "payments": "Cash, card terminal, bank transfer and approved customer credit.",
                    "delivery": "Delivery is agreed with the owner. No automatic delivery promises.",
                },
            )
            db.add_all([user, org])
            db.flush()
            db.add(Membership(user_id=user.id, organization_id=org.id, role="owner"))
            db.flush()
        ensure_main(db, org.id)
        warehouse = ensure_main(db, org.id)
        tenant = Tenant(org.id, user.id, "owner")
        existing = {
            p.sku
            for p in db.scalars(
                select(Product).where(Product.organization_id == org.id)
            )
        }
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
        examples = [
            ("DEMO-RICE", "Rice 1kg", "grocery", 25000, 18000, ["හාල් 1kg", "சாதம் 1kg"]),
            ("DEMO-SUGAR", "Sugar 1kg", "grocery", 23000, 17000, ["සීනි 1kg", "சீனி 1kg"]),
            ("DEMO-MILK", "Milk Powder", "grocery", 120000, 90000, ["කිරිපිටි", "பால்மா"]),
        ]
        created = 0
        for index in range(3000):
            if index < 3:
                sku, name, category, price, cost, aliases = examples[index]
            else:
                category = categories[(index - 3) % len(categories)]
                sku = f"DEMO-{index + 1:04d}"
                name = (
                    f"Demo {category.replace('_', ' ').title()} Product {index + 1:04d}"
                )
                cost = (index % 200 + 20) * 100
                price = cost + (index % 30 + 5) * 100
                aliases = []
            if sku in existing:
                continue
            product = Product(
                organization_id=org.id,
                sku=sku,
                name=name,
                category=category,
                price_minor=price,
                cost_minor=cost,
                wholesale_price_minor=price * 95 // 100,
                wholesale_min_qty=5,
                min_order_qty=1,
                barcode=f"200{index + 1:010d}",
                aliases=aliases,
                unit="units",
                stock=0,
                reorder_level=10,
                track_stock=True,
                active=True,
            )
            db.add(product)
            db.flush()
            move_stock(
                db, tenant, product, 100, warehouse, "Synthetic demo opening stock"
            )
            created += 1
        if not db.scalar(select(Customer.id).where(Customer.organization_id == org.id)):
            db.add_all(
                [
                    Customer(
                        organization_id=org.id,
                        name="Demo Retail Stores",
                        address="Demo Colombo",
                        credit_limit_minor=5_000_000,
                        payment_terms_days=14,
                        price_group="wholesale",
                    ),
                    Customer(
                        organization_id=org.id,
                        name="Demo Cash Buyer",
                        address="Demo Gampaha",
                    ),
                ]
            )
            db.add(
                Supplier(
                    organization_id=org.id,
                    name="Demo Trade Supplier",
                    address="Synthetic supplier",
                )
            )
        db.commit()
        access.parent.mkdir(exist_ok=True)
        access.write_text(
            json.dumps(
                {
                    "email": email,
                    "password": password,
                    "organization_id": org.id,
                    "url": "http://localhost:3000/sign-in",
                    "notice": "DEMO ONLY: synthetic products and prices; no live WhatsApp connection.",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "workspace": "OrderMesh Demo Wholesale",
                    "created_products": created,
                    "total_products": len(existing) + created,
                    "credentials_file": ".local/demo-access.json",
                    "whatsapp_connected": False,
                }
            )
        )


if __name__ == "__main__":
    main()
