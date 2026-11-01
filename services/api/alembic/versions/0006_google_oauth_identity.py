"""Store the verified Google subject for passwordless Google sign-in."""

from alembic import op
import sqlalchemy as sa


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    # A unique index supports nullable Google identities on both databases.
    # Avoid rebuilding users: existing memberships and sessions reference it.
    op.add_column("users", sa.Column("google_subject", sa.String(255), nullable=True))
    op.create_index("ix_users_google_subject", "users", ["google_subject"], unique=True)


def downgrade():
    op.drop_index("ix_users_google_subject", table_name="users")
    op.drop_column("users", "google_subject")
