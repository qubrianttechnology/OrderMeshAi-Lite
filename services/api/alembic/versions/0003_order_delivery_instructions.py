"""Store human-reviewed delivery instructions on confirmed orders."""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "orders",
        sa.Column(
            "delivery_instructions",
            sa.String(length=500),
            nullable=False,
            server_default="",
        ),
    )


def downgrade():
    op.drop_column("orders", "delivery_instructions")
