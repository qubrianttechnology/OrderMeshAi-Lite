"""Image caption and OCR uncertainty; original image bytes are not retained."""

import sqlalchemy as sa

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "whatsapp_messages",
        sa.Column("media_caption", sa.String(1024), nullable=False, server_default=""),
    )
    op.add_column(
        "whatsapp_messages",
        sa.Column(
            "media_uncertain", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade():
    op.drop_column("whatsapp_messages", "media_uncertain")
    op.drop_column("whatsapp_messages", "media_caption")
