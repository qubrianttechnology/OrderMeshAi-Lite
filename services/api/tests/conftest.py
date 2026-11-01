import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_db
from app.main import app, attempts


@pytest.fixture
def setup(monkeypatch):
    # Test clients must never inherit real provider credentials from the local .env.
    for name in [
        "whatsapp_verify_token",
        "meta_app_secret",
        "whatsapp_access_token",
        "meta_connection_encryption_key",
    ]:
        monkeypatch.setattr(settings, name, SecretStr(""))
    monkeypatch.setattr(settings, "ai_provider", "local")
    monkeypatch.setattr(settings, "allow_registration", True)
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    def override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override
    attempts.clear()
    with TestClient(app) as client:
        client.headers["X-OrderMesh"] = "1"
        yield client, factory
    app.dependency_overrides.clear()
    engine.dispose()


def register(client, suffix="one"):
    result = client.post(
        "/api/auth/register",
        json={
            "email": f"{suffix}@example.com",
            "password": "test-only-password-123",
            "name": "Test User",
            "organization_name": f"Org {suffix}",
        },
    )
    assert result.status_code == 201, result.text
    assert "HttpOnly" in result.headers["set-cookie"]
    assert "SameSite=strict" in result.headers["set-cookie"]
    client.headers["X-Organization-ID"] = result.json()["organization_id"]
    return result.json()


def catalog(client):
    customer = client.post(
        "/api/customers", json={"name": "Perera Stores", "address": "Colombo"}
    ).json()
    product = client.post(
        "/api/products",
        json={
            "name": "Rice",
            "sku": "RICE-1",
            "price_minor": 25000,
            "aliases": ["හාල්", "සහල්"],
        },
    ).json()
    assert (
        client.post(
            f"/api/products/{product['id']}/stock",
            json={"delta": 30, "reason": "Opening stock"},
        ).status_code
        == 200
    )
    return customer, product


def order_body(customer, product, quantity=2):
    return {
        "customer_id": customer["id"],
        "items": [{"product_id": product["id"], "quantity": quantity}],
        "human_confirmed": True,
        "expected_total_minor": int(max(quantity, 0) * product["price_minor"]),
    }
