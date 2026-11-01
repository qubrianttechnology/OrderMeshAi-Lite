"""Link WhatsApp conversations to deliberate customer phone identities.

Profile names from Meta are presentation data, not an identity proof. This
migration keeps old conversations unassigned until a deterministic match or a
team member explicitly links their international WhatsApp number.
"""

from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "customer_whatsapp_contacts",
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("phone", sa.String(length=15), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["organization_id", "customer_id"],
            ["customers.organization_id", "customers.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id"),
        sa.UniqueConstraint("organization_id", "phone"),
    )
    op.create_index(
        op.f("ix_customer_whatsapp_contacts_organization_id"),
        "customer_whatsapp_contacts",
        ["organization_id"],
        unique=False,
    )
    op.add_column(
        "whatsapp_conversations",
        sa.Column("customer_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "whatsapp_conversations",
        sa.Column(
            "customer_match_source",
            sa.String(length=24),
            nullable=False,
            server_default="unmatched",
        ),
    )
    with op.batch_alter_table(
        "whatsapp_conversations",
        table_args=(sa.CheckConstraint("unread_count >= 0"),),
    ) as batch_op:
        batch_op.create_foreign_key(
            "fk_whatsapp_conversations_customer",
            "customers",
            ["organization_id", "customer_id"],
            ["organization_id", "id"],
        )
        batch_op.create_check_constraint(
            "ck_whatsapp_conversations_customer_match_source",
            "customer_match_source IN ('unmatched','customer_phone','whatsapp_contact','manual')",
        )
    if op.get_bind().dialect.name == "postgresql":
        for table in ("customer_whatsapp_contacts",):
            op.execute(f"REVOKE ALL ON TABLE {table} FROM PUBLIC")
            for role in ("anon", "authenticated"):
                op.execute(
                    f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN REVOKE ALL ON TABLE {table} FROM {role}; END IF; END $$"
                )
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY tenant_isolation ON {table} "
                "USING (organization_id = current_setting('app.organization_id', true)) "
                "WITH CHECK (organization_id = current_setting('app.organization_id', true))"
            )


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON customer_whatsapp_contacts")
    with op.batch_alter_table(
        "whatsapp_conversations",
        table_args=(sa.CheckConstraint("unread_count >= 0"),),
    ) as batch_op:
        batch_op.drop_constraint(
            "ck_whatsapp_conversations_customer_match_source", type_="check"
        )
        batch_op.drop_constraint("fk_whatsapp_conversations_customer", type_="foreignkey")
    op.drop_column("whatsapp_conversations", "customer_match_source")
    op.drop_column("whatsapp_conversations", "customer_id")
    op.drop_index(
        op.f("ix_customer_whatsapp_contacts_organization_id"),
        table_name="customer_whatsapp_contacts",
    )
    op.drop_table("customer_whatsapp_contacts")
