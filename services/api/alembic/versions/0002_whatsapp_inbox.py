"""WhatsApp inbound routing, tenant-scoped inbox and durable processing queue."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TENANT_TABLES = (
    "whatsapp_conversations",
    "whatsapp_messages",
    "whatsapp_webhook_events",
)


def upgrade():
    op.create_table(
        "whatsapp_phone_numbers",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("phone_number_id", sa.String(128), nullable=False),
        sa.Column("display_phone_number", sa.String(40), nullable=False),
        sa.Column("business_account_id", sa.String(128), nullable=False),
        sa.Column("connected_by", sa.String(36), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["connected_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone_number_id"),
        sa.UniqueConstraint("organization_id", "phone_number_id"),
    )
    op.create_index(
        op.f("ix_whatsapp_phone_numbers_organization_id"),
        "whatsapp_phone_numbers",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "whatsapp_conversations",
        sa.Column("phone_number_id", sa.String(128), nullable=False),
        sa.Column("customer_phone", sa.String(40), nullable=False),
        sa.Column("customer_name", sa.String(120), nullable=False),
        sa.Column("last_message_preview", sa.String(500), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unread_count", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.CheckConstraint("unread_count >= 0"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["organization_id", "phone_number_id"],
            ["whatsapp_phone_numbers.organization_id", "whatsapp_phone_numbers.phone_number_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id"),
        sa.UniqueConstraint(
            "organization_id", "phone_number_id", "customer_phone"
        ),
    )
    op.create_index(
        op.f("ix_whatsapp_conversations_organization_id"),
        "whatsapp_conversations",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "whatsapp_messages",
        sa.Column("conversation_id", sa.String(36), nullable=False),
        sa.Column("phone_number_id", sa.String(128), nullable=False),
        sa.Column("external_id", sa.String(256), nullable=False),
        sa.Column("direction", sa.String(12), nullable=False),
        sa.Column("message_type", sa.String(20), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("customer_phone", sa.String(40), nullable=False),
        sa.Column("customer_name", sa.String(120), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("extraction_draft_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["organization_id", "conversation_id"],
            ["whatsapp_conversations.organization_id", "whatsapp_conversations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "phone_number_id"],
            ["whatsapp_phone_numbers.organization_id", "whatsapp_phone_numbers.phone_number_id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "extraction_draft_id"],
            ["extraction_drafts.organization_id", "extraction_drafts.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("direction IN ('inbound','outbound')"),
        sa.UniqueConstraint("organization_id", "id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index(
        op.f("ix_whatsapp_messages_organization_id"),
        "whatsapp_messages",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "whatsapp_webhook_events",
        sa.Column("external_id", sa.String(256), nullable=False),
        sa.Column("message_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued','processing','processed','failed')"
        ),
        sa.CheckConstraint("attempts >= 0"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["organization_id", "message_id"],
            ["whatsapp_messages.organization_id", "whatsapp_messages.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index(
        op.f("ix_whatsapp_webhook_events_organization_id"),
        "whatsapp_webhook_events",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_whatsapp_webhook_queue",
        "whatsapp_webhook_events",
        ["status", "created_at"],
    )
    if op.get_bind().dialect.name == "postgresql":
        for table in (
            "whatsapp_phone_numbers",
            *TENANT_TABLES,
        ):
            op.execute(f"REVOKE ALL ON TABLE {table} FROM PUBLIC")
            for role in ("anon", "authenticated"):
                op.execute(
                    f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN REVOKE ALL ON TABLE {table} FROM {role}; END IF; END $$"
                )
        for table in TENANT_TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY tenant_isolation ON {table} "
                "USING (organization_id = current_setting('app.organization_id', true)) "
                "WITH CHECK (organization_id = current_setting('app.organization_id', true))"
            )


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        for table in TENANT_TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    op.drop_index("ix_whatsapp_webhook_queue", table_name="whatsapp_webhook_events")
    op.drop_index(
        op.f("ix_whatsapp_webhook_events_organization_id"),
        table_name="whatsapp_webhook_events",
    )
    op.drop_table("whatsapp_webhook_events")
    op.drop_index(
        op.f("ix_whatsapp_messages_organization_id"), table_name="whatsapp_messages"
    )
    op.drop_table("whatsapp_messages")
    op.drop_index(
        op.f("ix_whatsapp_conversations_organization_id"),
        table_name="whatsapp_conversations",
    )
    op.drop_table("whatsapp_conversations")
    op.drop_index(
        op.f("ix_whatsapp_phone_numbers_organization_id"),
        table_name="whatsapp_phone_numbers",
    )
    op.drop_table("whatsapp_phone_numbers")
