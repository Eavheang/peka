"""create user invitations

Revision ID: 017_create_invitations
Revises: 016_add_user_display_name
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "017_create_invitations"
down_revision: Union[str, None] = "016_add_user_display_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'senior', 'staff')", name="invitations_role_check"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="invitations_token_hash_key"),
    )
    # One pending invitation per address; accepted rows stay as history.
    op.create_index(
        "invitations_pending_email_key",
        "invitations",
        [sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("accepted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("invitations_pending_email_key", table_name="invitations")
    op.drop_table("invitations")
