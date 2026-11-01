import pytest
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.config import Settings


def test_local_development_defaults_to_sqlite():
    settings = Settings(
        _env_file=None,
        database_url=None,
        migration_database_url="",
    )

    assert settings.runtime_database_url == "sqlite:///./ordermesh.db"
    assert settings.resolved_migration_database_url == settings.runtime_database_url


def test_migration_url_overrides_runtime_for_alembic_but_same_target_is_required():
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://runtime:runtime-pass@db.example.invalid:5432/orders",
        migration_database_url="postgresql+psycopg://migrator:migration-pass@db.example.invalid:5432/orders",
    )

    assert make_url(settings.runtime_database_url).username == "runtime"
    assert make_url(settings.resolved_migration_database_url).username == "migrator"


def test_environment_database_urls_are_used_and_explicit_values_take_precedence(
    monkeypatch,
):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://environment:env-pass@db.example.invalid/orders",
    )
    monkeypatch.setenv(
        "MIGRATION_DATABASE_URL",
        "postgresql+psycopg://migrator:migration-pass@db.example.invalid/orders",
    )
    from_environment = Settings(_env_file=None)
    explicit = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://runtime:runtime-pass@db.example.invalid/orders",
        migration_database_url="postgresql+psycopg://explicit:explicit-pass@db.example.invalid/orders",
    )

    assert make_url(from_environment.runtime_database_url).username == "environment"
    assert (
        make_url(from_environment.resolved_migration_database_url).username
        == "migrator"
    )
    assert make_url(explicit.runtime_database_url).username == "runtime"
    assert make_url(explicit.resolved_migration_database_url).username == "explicit"


def test_migration_url_may_use_a_different_supabase_endpoint_for_same_target():
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://runtime:runtime-pass@pool.example.invalid:6543/orders",
        migration_database_url="postgresql+psycopg://migrator:migration-pass@direct.example.invalid:5432/orders",
        database_target_id="development-project",
        migration_database_target_id="development-project",
    )

    assert (
        make_url(settings.resolved_migration_database_url).host
        == "direct.example.invalid"
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "database_url": "sqlite:///./ordermesh.db",
            "migration_database_url": "postgresql+psycopg://migrator:fake@db.example.invalid/orders",
        },
        {
            "database_url": "postgresql+psycopg://runtime:fake@db.example.invalid/orders",
            "migration_database_url": "postgresql+psycopg://migrator:fake@db.example.invalid/other",
        },
        {
            "database_url": "postgresql+psycopg://runtime:fake@runtime.example.invalid/orders",
            "migration_database_url": "postgresql+psycopg://migrator:fake@migration.example.invalid/orders",
        },
    ],
)
def test_mismatched_runtime_and_migration_targets_are_rejected(overrides):
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, **overrides)

    message = str(error.value)
    assert "same database" in message or "DATABASE_TARGET_ID" in message
    assert "fake" not in message


def test_production_rejects_sqlite():
    with pytest.raises(ValidationError, match="Production requires PostgreSQL"):
        Settings(
            _env_file=None,
            app_env="production",
            app_origin="https://orders.example.com",
            database_url="sqlite:///./ordermesh.db",
        )


def test_production_requires_migration_url_when_alembic_url_is_resolved():
    settings = Settings(
        _env_file=None,
        app_env="production",
        app_origin="https://orders.example.com",
        database_url="postgresql+psycopg://runtime:fake@db.example.invalid/orders?sslmode=require",
        migration_database_url="",
    )

    with pytest.raises(ValueError, match="MIGRATION_DATABASE_URL is required"):
        _ = settings.resolved_migration_database_url


def test_invalid_database_url_error_does_not_echo_url():
    private_value = "postgresql://user:fake-secret@["
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, database_url=private_value)

    assert private_value not in str(error.value)
    assert "DATABASE_URL must include a PostgreSQL host and database name" in str(
        error.value
    )


def test_postgresql_url_requires_host_and_database_name():
    with pytest.raises(ValidationError, match="host and database name"):
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://",
        )
