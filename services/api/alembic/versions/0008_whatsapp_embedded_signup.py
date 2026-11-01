"""Encrypted per-workspace Meta connections and short-lived signup attempts."""

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "whatsapp_phone_numbers",
        sa.Column(
            "access_token_encrypted", sa.Text(), nullable=False, server_default=""
        ),
    )
    op.add_column(
        "whatsapp_phone_numbers",
        sa.Column(
            "connection_kind", sa.String(24), nullable=False, server_default="manual"
        ),
    )
    op.create_table(
        "whatsapp_signup_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("session_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("token_encrypted", sa.Text(), nullable=False),
        sa.Column("choices", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_whatsapp_signup_attempts_organization_id",
        "whatsapp_signup_attempts",
        ["organization_id"],
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("REVOKE ALL ON TABLE whatsapp_signup_attempts FROM PUBLIC")
        for role in ("anon", "authenticated"):
            op.execute(
                f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN REVOKE ALL ON TABLE whatsapp_signup_attempts FROM {role}; END IF; END $$"
            )
        op.execute("ALTER TABLE whatsapp_signup_attempts ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE whatsapp_signup_attempts FORCE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY tenant_isolation ON whatsapp_signup_attempts USING (organization_id=current_setting('app.organization_id',true)) WITH CHECK (organization_id=current_setting('app.organization_id',true))"
        )


def downgrade():
    op.drop_index(
        "ix_whatsapp_signup_attempts_organization_id",
        table_name="whatsapp_signup_attempts",
    )
    op.drop_table("whatsapp_signup_attempts")
    op.drop_column("whatsapp_phone_numbers", "connection_kind")
    op.drop_column("whatsapp_phone_numbers", "access_token_encrypted")
