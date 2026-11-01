import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError

from app import seed as sample
from app.models import Base


@pytest.mark.parametrize("existing_account", [False, True])
def test_migrations_match_models_and_can_rollback(existing_account):
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    versions = Path(__file__).parents[1] / "alembic/versions"
    modules = []
    for revision, filename in (
        ("initial_migration", "0001_initial.py"),
        ("whatsapp_migration", "0002_whatsapp_inbox.py"),
        ("delivery_instructions_migration", "0003_order_delivery_instructions.py"),
        ("whatsapp_cloud_migration", "0004_whatsapp_cloud_send_status.py"),
        ("customer_whatsapp_identity_migration", "0005_customer_whatsapp_identity.py"),
        ("google_oauth_identity_migration", "0006_google_oauth_identity.py"),
        ("business_subscriptions_migration", "0007_business_subscriptions.py"),
        ("embedded_signup_migration", "0008_whatsapp_embedded_signup.py"),
        ("voice_migration", "0009_voice_transcription.py"),
        ("image_migration", "0010_image_extraction.py"),
        ("wholesale_migration", "0011_wholesale_categories.py"),
        ("bot_reply_migration", "0012_whatsapp_bot_replies.py"),
        ("notification_migration", "0013_notification_reads.py"),
        ("commerce_migration", "0014_commerce_operations.py"),
        ("settings_migration", "0015_account_and_inbox_settings.py"),
    ):
        spec = importlib.util.spec_from_file_location(revision, versions / filename)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            for module in modules:
                if existing_account and module.revision == "0006":
                    connection.execute(
                        text(
                            "INSERT INTO users (id,email,name,password_hash) "
                            "VALUES ('u','migration@example.com','Existing User','test-hash')"
                        )
                    )
                    connection.execute(
                        text(
                            "INSERT INTO organizations "
                            "(id,name,plan,subscription_status,monthly_order_limit) "
                            "VALUES ('o','Existing Workspace','starter','trial',500)"
                        )
                    )
                    connection.execute(
                        text(
                            "INSERT INTO memberships (user_id,organization_id,role) "
                            "VALUES ('u','o','owner')"
                        )
                    )
                    connection.execute(
                        text(
                            "INSERT INTO sessions (token_hash,user_id,expires_at) "
                            "VALUES ('existing-session','u','2099-01-01 00:00:00')"
                        )
                    )
                if existing_account and module.revision == "0011":
                    connection.execute(
                        text(
                            "INSERT INTO products (id,organization_id,sku,name,aliases,unit,price_minor,stock,reorder_level,active,track_stock) VALUES ('p','o','OLD-PART','Existing part','[]','pieces',15000,7,2,1,1)"
                        )
                    )
                module.upgrade()
            if existing_account:
                assert connection.execute(
                    text("SELECT category,stock,price_minor FROM products WHERE id='p'")
                ).one() == ("other", 7, 15000)
            if existing_account:
                assert (
                    connection.scalar(
                        text(
                            "SELECT quantity FROM warehouse_balances WHERE product_id='p' AND organization_id='o'"
                        )
                    )
                    == 7
                )
                assert (
                    connection.scalar(
                        text("SELECT code FROM warehouses WHERE organization_id='o'")
                    )
                    == "MAIN"
                )
            assert compare_metadata(context, Base.metadata) == []
            if existing_account:
                connection.execute(
                    text(
                        "UPDATE users SET google_subject='google-subject' WHERE id='u'"
                    )
                )
                with pytest.raises(IntegrityError), connection.begin_nested():
                    connection.execute(
                        text(
                            "INSERT INTO users (id,email,name,password_hash,google_subject) "
                            "VALUES ('other','other@example.com','Other','hash','google-subject')"
                        )
                    )
                assert (
                    connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
                )
            for module in reversed(modules):
                module.downgrade()
                if existing_account and module.revision == "0006":
                    assert connection.scalar(text("SELECT count(*) FROM users")) == 1
                    assert (
                        connection.scalar(text("SELECT user_id FROM memberships"))
                        == "u"
                    )
                    assert (
                        connection.scalar(text("SELECT user_id FROM sessions")) == "u"
                    )
                    assert (
                        connection.exec_driver_sql("PRAGMA foreign_key_check").all()
                        == []
                    )
            assert inspect(connection).get_table_names() == []


def test_sample_data_is_isolated_and_does_not_overwrite(setup, monkeypatch):
    client, factory = setup
    monkeypatch.setattr(sample, "SessionLocal", factory)
    org = sample.seed("sample@example.com", "sample-test-password-123")
    response = client.post(
        "/api/auth/login",
        json={"email": "sample@example.com", "password": "sample-test-password-123"},
    )
    assert response.status_code == 200
    client.headers["X-Organization-ID"] = org
    assert len(client.get("/api/products").json()) == 8
    assert len(client.get("/api/customers").json()) == 5
    assert len(client.get("/api/orders").json()) == 14
    with pytest.raises(ValueError, match="already exists"):
        sample.seed("sample@example.com", "sample-test-password-123")


def test_sample_seed_refuses_non_sqlite_databases(monkeypatch):
    class Session:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(sample, "SessionLocal", Session)

    with pytest.raises(RuntimeError, match="restricted to local SQLite"):
        sample.seed("demo@example.com", "test-only-password-123")
