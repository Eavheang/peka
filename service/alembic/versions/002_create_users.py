"""create users table

Revision ID: 002_create_users
Revises: 001_create_todos
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_create_users"
down_revision: Union[str, None] = "001_create_todos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(10), nullable=False, server_default="member"),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("role IN ('member', 'admin')", name="users_role_check"),
        sa.CheckConstraint("token_version >= 0", name="users_token_version_check"),
    )
    op.create_index("users_email_lower_key", "users", [sa.text("lower(email)")], unique=True)


def downgrade() -> None:
    op.drop_index("users_email_lower_key", table_name="users")
    op.drop_table("users")
