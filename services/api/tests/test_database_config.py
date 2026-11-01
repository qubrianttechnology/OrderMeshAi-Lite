import pytest
from sqlalchemy.engine import make_url

from app.db import normalize_database_url


@pytest.mark.parametrize(
    "value",
    [
        "postgres://user:pass@db.example.com/orders?sslmode=require",
        "postgresql://user:pass@db.example.com/orders?sslmode=require",
    ],
)
def test_postgresql_urls_use_psycopg3(value):
    normalized = make_url(normalize_database_url(value))
    assert normalized.drivername == "postgresql+psycopg"
    assert normalized.host == "db.example.com"
    assert normalized.query["sslmode"] == "require"


def test_existing_psycopg_url_is_preserved():
    value = "postgresql+psycopg://user:pass@db.example.com/orders?sslmode=require"
    assert normalize_database_url(value) == value


def test_sqlite_url_is_preserved():
    value = "sqlite:///./ordermesh.db"
    assert normalize_database_url(value) == value


def test_unsupported_postgresql_driver_is_rejected():
    with pytest.raises(ValueError, match="Psycopg 3"):
        normalize_database_url("postgresql+asyncpg://user:pass@db.example.com/orders")
