"""Account photos and conversation management, preserving existing records."""

from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users", sa.Column("phone", sa.String(40), nullable=False, server_default="")
    )
    op.add_column("users", sa.Column("avatar_data", sa.LargeBinary(), nullable=True))
    op.add_column(
        "users",
        sa.Column("avatar_mime", sa.String(40), nullable=False, server_default=""),
    )
    op.add_column(
        "whatsapp_conversations",
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "whatsapp_conversations",
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column("whatsapp_conversations", "pinned")
    op.drop_column("whatsapp_conversations", "archived")
    op.drop_column("users", "avatar_mime")
    op.drop_column("users", "avatar_data")
    op.drop_column("users", "phone")
