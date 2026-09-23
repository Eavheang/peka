"""add user display names

Revision ID: 016_add_user_display_name
Revises: 015_create_provider_settings
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "016_add_user_display_name"
down_revision: Union[str, None] = "015_create_provider_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(100), server_default="", nullable=False))


def downgrade() -> None:
    op.drop_column("users", "display_name")
