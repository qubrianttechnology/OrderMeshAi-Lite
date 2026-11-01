"""Voice metadata and reviewable transcription; raw audio is not retained."""

import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    for name, length in [
        ("media_id", 128),
        ("media_mime_type", 100),
        ("media_sha256", 64),
        ("transcription_status", 20),
        ("transcription_error", 240),
    ]:
        op.add_column(
            "whatsapp_messages",
            sa.Column(name, sa.String(length), nullable=False, server_default=""),
        )


def downgrade():
    for name in [
        "transcription_error",
        "transcription_status",
        "media_sha256",
        "media_mime_type",
        "media_id",
    ]:
        op.drop_column("whatsapp_messages", name)
