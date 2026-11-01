"""Durable, tenant-scoped WhatsApp chatbot reply queue."""

import sqlalchemy as sa

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "whatsapp_bot_replies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("source_message_id", sa.String(36), nullable=False),
        sa.Column("request_key", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("last_error", sa.String(240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "request_key"),
        sa.ForeignKeyConstraint(
            ["organization_id", "source_message_id"],
            ["whatsapp_messages.organization_id", "whatsapp_messages.id"],
        ),
        sa.CheckConstraint(
            "status IN ('queued','sending','accepted','blocked','unknown','cancelled')"
        ),
    )
    op.create_index(
        "ix_whatsapp_bot_replies_organization_id",
        "whatsapp_bot_replies",
        ["organization_id"],
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("REVOKE ALL ON TABLE whatsapp_bot_replies FROM PUBLIC")
        for role in ("anon", "authenticated"):
            op.execute(
                f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN REVOKE ALL ON TABLE whatsapp_bot_replies FROM {role}; END IF; END $$"
            )
        op.execute("ALTER TABLE whatsapp_bot_replies ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE whatsapp_bot_replies FORCE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY tenant_isolation ON whatsapp_bot_replies USING (organization_id=current_setting('app.organization_id',true)) WITH CHECK (organization_id=current_setting('app.organization_id',true))"
        )


def downgrade():
    op.drop_index(
        "ix_whatsapp_bot_replies_organization_id", table_name="whatsapp_bot_replies"
    )
    op.drop_table("whatsapp_bot_replies")
