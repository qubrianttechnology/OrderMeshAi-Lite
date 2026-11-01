"""Persist outbound WhatsApp replies and delivery status."""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "whatsapp_messages",
        sa.Column("delivery_status", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "whatsapp_messages",
        sa.Column("status_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "whatsapp_messages",
        sa.Column(
            "delivery_error_code",
            sa.String(length=40),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "whatsapp_messages",
        sa.Column(
            "delivery_error_message",
            sa.String(length=500),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "whatsapp_messages",
        sa.Column("client_request_id", sa.String(length=80), nullable=True),
    )
    with op.batch_alter_table(
        "whatsapp_messages",
        table_args=(sa.CheckConstraint("direction IN ('inbound','outbound')"),),
    ) as batch_op:
        batch_op.create_unique_constraint(
            "uq_whatsapp_messages_org_client_request",
            ["organization_id", "client_request_id"],
        )


def downgrade():
    with op.batch_alter_table(
        "whatsapp_messages",
        table_args=(sa.CheckConstraint("direction IN ('inbound','outbound')"),),
    ) as batch_op:
        batch_op.drop_constraint(
            "uq_whatsapp_messages_org_client_request",
            type_="unique",
        )
    op.drop_column("whatsapp_messages", "client_request_id")
    op.drop_column("whatsapp_messages", "delivery_error_message")
    op.drop_column("whatsapp_messages", "delivery_error_code")
    op.drop_column("whatsapp_messages", "status_updated_at")
    op.drop_column("whatsapp_messages", "delivery_status")
