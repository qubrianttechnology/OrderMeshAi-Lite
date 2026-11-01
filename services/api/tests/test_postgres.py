"""Run only against a disposable DB explicitly supplied via TEST_POSTGRES_URL.

Uses a randomly named schema and runtime role, removed at teardown.
The test connection must be a test-only admin able to CREATE ROLE.
"""

import importlib.util
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker

from app.main import create_order
from app.models import Order, Product
from app.schemas import OrderInput
from app.security import Tenant

pytestmark = pytest.mark.postgres


@pytest.fixture
def postgres():
    url = os.environ.get("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL is not configured")
    if os.environ.get("TEST_POSTGRES_DISPOSABLE") != "YES":
        pytest.skip(
            "Set TEST_POSTGRES_DISPOSABLE=YES only for a dedicated disposable test database"
        )
    engine = create_engine(url)
    name = "om_test_" + uuid.uuid4().hex
    role = name + "_role"
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {name}"))
        conn.execute(text(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS"))
        conn.execute(text(f"SET LOCAL search_path TO {name}"))
        versions = Path(__file__).parents[1] / "alembic/versions"
        with Operations.context(MigrationContext.configure(conn)):
            for revision, filename in (
                ("migration_v1", "0001_initial.py"),
                ("migration_v2", "0002_whatsapp_inbox.py"),
                ("migration_v3", "0003_order_delivery_instructions.py"),
                ("migration_v4", "0004_whatsapp_cloud_send_status.py"),
                ("migration_v5", "0005_customer_whatsapp_identity.py"),
                ("migration_v6", "0006_google_oauth_identity.py"),
                ("migration_v7", "0007_business_subscriptions.py"),
                ("migration_v8", "0008_whatsapp_embedded_signup.py"),
                ("migration_v9", "0009_voice_transcription.py"),
                ("migration_v10", "0010_image_extraction.py"),
                ("wholesale_migration", "0011_wholesale_categories.py"),
                ("bot_reply_migration", "0012_whatsapp_bot_replies.py"),
                ("notification_migration", "0013_notification_reads.py"),
                ("commerce_migration", "0014_commerce_operations.py"),
                ("settings_migration", "0015_account_and_inbox_settings.py"),
            ):
                spec = importlib.util.spec_from_file_location(
                    revision, versions / filename
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.upgrade()
        conn.execute(text(f"GRANT USAGE ON SCHEMA {name} TO {role}"))
        conn.execute(
            text(
                f"GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA {name} TO {role}"
            )
        )
        conn.execute(
            text(
                "INSERT INTO organizations(id,name,plan,subscription_status,monthly_order_limit) VALUES ('a','A','starter','trial',500),('b','B','starter','trial',500)"
            )
        )
        conn.execute(
            text(
                "UPDATE organizations SET trial_started_at=CURRENT_TIMESTAMP, trial_ends_at=CURRENT_TIMESTAMP + INTERVAL '15 days'"
            )
        )
        conn.execute(
            text(
                "INSERT INTO users(id,email,name,password_hash) VALUES ('user-a','a@example.com','A','test'),('user-b','b@example.com','B','test')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO memberships(user_id,organization_id,role) VALUES ('user-a','a','owner'),('user-b','b','owner')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO customers(id,organization_id,name,phone,address,active) VALUES ('customer-a','a','A','','',true),('customer-b','b','B','','',true)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO products(id,organization_id,sku,name,aliases,unit,price_minor,stock,reorder_level,active) VALUES ('product-a','a','A','Rice','[]','bags',100,3,1,true),('product-b','b','B','Sugar','[]','bags',200,5,1,true)"
            )
        )
    runtime = create_engine(url)

    @event.listens_for(runtime, "begin")
    def role_and_schema(conn):
        conn.exec_driver_sql(f"SET LOCAL ROLE {role}")
        conn.exec_driver_sql(f"SET LOCAL search_path TO {name}")

    try:
        yield runtime
    finally:
        runtime.dispose()
        with engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {name} CASCADE"))
            conn.execute(text(f"DROP ROLE {role}"))
        engine.dispose()


def test_postgres_rls_denies_unscoped_reads_and_foreign_writes(postgres):
    with postgres.begin() as conn:
        active_role = conn.execute(
            text(
                "SELECT current_user, r.rolsuper, r.rolbypassrls "
                "FROM pg_roles r WHERE r.rolname = current_user"
            )
        ).one()
        assert active_role.current_user.endswith("_role")
        assert active_role.rolsuper is False
        assert active_role.rolbypassrls is False
        for table in (
            "notification_reads",
            "suppliers",
            "warehouses",
            "warehouse_balances",
            "purchases",
            "customer_payments",
            "expenses",
            "sales_returns",
            "stock_transfers",
        ):
            assert conn.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0
            assert (
                conn.execute(
                    text(
                        "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid=to_regclass(:table)"
                    ),
                    {"table": table},
                ).scalar()
                is True
            )
        assert conn.execute(text("SELECT count(*) FROM products")).scalar() == 0
        conn.execute(text("SELECT set_config('app.organization_id','a',true)"))
        assert conn.execute(text("SELECT id FROM products")).scalars().all() == [
            "product-a"
        ]
        assert (
            conn.execute(
                text("UPDATE products SET stock=999 WHERE id='product-b'")
            ).rowcount
            == 0
        )
        with pytest.raises(Exception):
            conn.execute(
                text(
                    "INSERT INTO customers(id,organization_id,name,phone,address,active) VALUES ('evil','b','Evil','','',true)"
                )
            )
    with postgres.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM products")).scalar() == 0


def test_postgres_whatsapp_tables_enforce_tenant_rls(postgres):
    with postgres.begin() as conn:
        for table in (
            "whatsapp_conversations",
            "whatsapp_messages",
            "whatsapp_webhook_events",
        ):
            assert conn.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0
        conn.execute(text("SELECT set_config('app.organization_id','a',true)"))
        conn.execute(
            text(
                "INSERT INTO whatsapp_phone_numbers "
                "(id,organization_id,phone_number_id,display_phone_number,business_account_id,connected_by,active,created_at) "
                "VALUES ('phone-a','a','123456789012345','+94770001122','business-a','user-a',true,now())"
            )
        )
        conn.execute(
            text(
                "INSERT INTO whatsapp_conversations "
                "(id,organization_id,phone_number_id,customer_phone,customer_name,last_message_preview,last_message_at,unread_count) "
                "VALUES ('conversation-a','a','123456789012345','94770001122','Nimal','Rice 2',now(),1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO whatsapp_messages "
                "(id,organization_id,conversation_id,phone_number_id,external_id,direction,message_type,text,customer_phone,customer_name,sent_at,created_at,updated_at) "
                "VALUES ('message-a','a','conversation-a','123456789012345','wamid.test','inbound','text','Rice 2','94770001122','Nimal',now(),now(),now())"
            )
        )
        conn.execute(
            text(
                "INSERT INTO whatsapp_webhook_events "
                "(id,organization_id,external_id,message_id,status,attempts,last_error,created_at) "
                "VALUES ('event-a','a','wamid.test','message-a','queued',0,'',now())"
            )
        )
        assert (
            conn.execute(text("SELECT count(*) FROM whatsapp_messages")).scalar() == 1
        )
        conn.execute(text("SELECT set_config('app.organization_id','b',true)"))
        for table in (
            "whatsapp_conversations",
            "whatsapp_messages",
            "whatsapp_webhook_events",
        ):
            assert conn.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0
        with pytest.raises(Exception):
            conn.execute(
                text(
                    "INSERT INTO whatsapp_conversations "
                    "(id,organization_id,phone_number_id,customer_phone,customer_name,last_message_preview,last_message_at,unread_count) "
                    "VALUES ('foreign','a','123456789012345','1','foreign','x',now(),1)"
                )
            )


def test_postgres_concurrent_orders_cannot_oversell(postgres):
    factory = sessionmaker(postgres, expire_on_commit=False)

    def place(index):
        with factory() as db:
            db.execute(text("SELECT set_config('app.organization_id','a',true)"))
            body = OrderInput(
                customer_id="customer-a",
                items=[{"product_id": "product-a", "quantity": 2}],
                human_confirmed=True,
                expected_total_minor=200,
            )
            try:
                create_order(
                    body, f"concurrent-{index}", Tenant("a", "user-a", "owner"), db
                )
                return 201
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(place, range(2))) == [201, 409]
    with factory() as db:
        db.execute(text("SELECT set_config('app.organization_id','a',true)"))
        assert (
            db.scalar(
                select(Product.stock).where(
                    Product.organization_id == "a", Product.id == "product-a"
                )
            )
            == 1
        )
        assert (
            len(list(db.scalars(select(Order).where(Order.organization_id == "a"))))
            == 1
        )
