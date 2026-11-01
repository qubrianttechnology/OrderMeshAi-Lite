import pytest
from pydantic import ValidationError

from app.config import Settings


def test_app_environment_rejects_unrecognized_values():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="prod")


@pytest.mark.parametrize(
    ("database_url", "app_origin"),
    [
        ("sqlite:///./ordermesh.db", "https://orders.example.com"),
        ("postgresql://app:pass@db.example.com/orders", "http://orders.example.com"),
    ],
)
def test_production_requires_postgresql_and_https(database_url, app_origin):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            database_url=database_url,
            app_origin=app_origin,
        )


def test_production_requires_postgresql_tls():
    with pytest.raises(ValidationError, match="requires TLS"):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql://app:pass@db.example.com/orders",
            app_origin="https://orders.example.com",
        )


def test_production_accepts_postgresql_and_https():
    settings = Settings(
        _env_file=None,
        app_env="production",
        database_url="postgresql://app:pass@db.example.com/orders?sslmode=require",
        app_origin="https://orders.example.com",
    )
    assert settings.app_env == "production"


def test_production_requires_explicit_database_url_without_exposing_it():
    with pytest.raises(ValidationError) as error:
        Settings(
            _env_file=None,
            app_env="production",
            app_origin="https://orders.example.com",
            database_url=None,
            migration_database_url="",
        )
    message = str(error.value)
    assert "DATABASE_URL must be explicitly configured" in message
    assert "password" not in message.lower()


@pytest.mark.parametrize(
    ("pool_size", "overflow", "timeout"),
    [(0, 1, 30), (5, -1, 30), (5, 0, 0)],
)
def test_database_pool_settings_are_validated(pool_size, overflow, timeout):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            db_pool_size=pool_size,
            db_max_overflow=overflow,
            db_pool_timeout=timeout,
        )
