import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Base, Customer, Order, Organization, Product, User


def test_database_rejects_negative_stock_and_cross_tenant_customer():
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all(
            [
                Organization(id="a", name="A"),
                Organization(id="b", name="B"),
                User(
                    id="u", email="schema@example.com", name="U", password_hash="test"
                ),
            ]
        )
        db.commit()
        db.add(Product(organization_id="a", sku="X", name="X", price_minor=1, stock=-1))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(Customer(id="c", organization_id="b", name="C"))
        db.commit()
        db.add(
            Order(
                organization_id="a",
                customer_id="c",
                customer_name="C",
                customer_address="",
                total_minor=1,
                created_by="u",
                idempotency_key="x",
                request_hash="x",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
