"""Business profiles, service catalogs, message filtering and subscriptions."""

from datetime import datetime, timedelta, timezone
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    for column in [
        sa.Column(
            "business_type", sa.String(32), nullable=False, server_default="retail"
        ),
        sa.Column(
            "business_profile",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_until", sa.DateTime(timezone=True), nullable=True),
    ]:
        op.add_column("organizations", column)
    current = datetime.now(timezone.utc)
    org = sa.table(
        "organizations",
        sa.column("trial_started_at", sa.DateTime(timezone=True)),
        sa.column("trial_ends_at", sa.DateTime(timezone=True)),
        sa.column("paid_until", sa.DateTime(timezone=True)),
        sa.column("subscription_status", sa.String()),
    )
    op.execute(
        org.update().values(
            trial_started_at=current, trial_ends_at=current + timedelta(days=15)
        )
    )
    op.execute(
        org.update()
        .where(org.c.subscription_status == "active")
        .values(paid_until=current + timedelta(days=31))
    )
    for table in ("products", "order_lines"):
        op.add_column(
            table,
            sa.Column(
                "track_stock", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
        )
    op.add_column(
        "whatsapp_messages",
        sa.Column(
            "category", sa.String(32), nullable=False, server_default="unclassified"
        ),
    )
    op.add_column(
        "whatsapp_messages",
        sa.Column("category_reason", sa.String(240), nullable=False, server_default=""),
    )
    op.add_column(
        "whatsapp_messages",
        sa.Column(
            "category_reviewed", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_table(
        "billing_checkout_routes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
    )
    op.create_table(
        "billing_checkouts",
        sa.Column("entitled_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("customer_details", sa.JSON(), nullable=False),
        sa.Column("subscription_id", sa.String(80), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("verified_payments", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_billing_checkouts_organization_id", "billing_checkouts", ["organization_id"]
    )
    if op.get_bind().dialect.name == "postgresql":
        for table in ("billing_checkouts", "billing_checkout_routes"):
            op.execute(f"REVOKE ALL ON TABLE {table} FROM PUBLIC")
            for role in ("anon", "authenticated"):
                op.execute(
                    f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN REVOKE ALL ON TABLE {table} FROM {role}; END IF; END $$"
                )
        op.execute("ALTER TABLE billing_checkouts ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE billing_checkouts FORCE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY tenant_isolation ON billing_checkouts USING (organization_id=current_setting('app.organization_id',true)) WITH CHECK (organization_id=current_setting('app.organization_id',true))"
        )


def downgrade():
    op.drop_index(
        "ix_billing_checkouts_organization_id", table_name="billing_checkouts"
    )
    op.drop_table("billing_checkouts")
    op.drop_table("billing_checkout_routes")
    for column in ("category_reviewed", "category_reason", "category"):
        op.drop_column("whatsapp_messages", column)
    for table in ("products", "order_lines"):
        op.drop_column(table, "track_stock")
    for column in (
        "paid_until",
        "trial_ends_at",
        "trial_started_at",
        "business_profile",
        "business_type",
    ):
        op.drop_column("organizations", column)
