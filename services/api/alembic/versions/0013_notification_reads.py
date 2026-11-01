"""Per-user read state for actionable workspace notifications."""

import sqlalchemy as sa

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notification_reads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_key", sa.String(64), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id", "event_key"),
    )
    op.create_index(
        "ix_notification_reads_organization_id",
        "notification_reads",
        ["organization_id"],
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("REVOKE ALL ON TABLE notification_reads FROM PUBLIC")
        for role in ("anon", "authenticated"):
            op.execute(
                f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN REVOKE ALL ON TABLE notification_reads FROM {role}; END IF; END $$"
            )
        op.execute("ALTER TABLE notification_reads ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE notification_reads FORCE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY tenant_isolation ON notification_reads USING (organization_id=current_setting('app.organization_id',true)) WITH CHECK (organization_id=current_setting('app.organization_id',true))"
        )


def downgrade():
    op.drop_index(
        "ix_notification_reads_organization_id", table_name="notification_reads"
    )
    op.drop_table("notification_reads")
