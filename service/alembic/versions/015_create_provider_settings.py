"""persist admin-managed provider settings

Revision ID: 015_create_provider_settings
Revises: 014_add_conversation_pagination_index
"""
from typing import Sequence, Union

from alembic import op

revision: str = "015_create_provider_settings"
down_revision: Union[str, None] = "014_add_conversation_pagination_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TABLE provider_settings (id SMALLINT PRIMARY KEY CHECK (id = 1), value JSONB NOT NULL)")


def downgrade() -> None:
    op.drop_table("provider_settings")
