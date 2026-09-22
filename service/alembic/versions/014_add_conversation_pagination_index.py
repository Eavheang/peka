"""index conversations for cursor pagination

Revision ID: 014_add_conversation_pagination_index
Revises: 013_create_chat_tables
"""
from typing import Sequence, Union

from alembic import op


revision: str = "014_add_conversation_pagination_index"
down_revision: Union[str, None] = "013_create_chat_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "conversations_owner_updated_at_id_idx",
        "conversations",
        ["owner_id", "updated_at", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "conversations_owner_updated_at_id_idx",
        table_name="conversations",
    )
