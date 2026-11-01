"""Wholesale catalog categories; existing products remain uncategorized."""

import sqlalchemy as sa

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "products",
        sa.Column("category", sa.String(32), nullable=False, server_default="other"),
    )


def downgrade():
    op.drop_column("products", "category")
