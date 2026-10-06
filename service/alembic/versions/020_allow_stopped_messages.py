"""allow stopped assistant messages

Revision ID: 020_allow_stopped_messages
Revises: 019_create_google_drive
"""
from typing import Sequence, Union

from alembic import op


revision: str = "020_allow_stopped_messages"
down_revision: Union[str, None] = "019_create_google_drive"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("messages_status_check", "messages", type_="check")
    op.create_check_constraint("messages_status_check", "messages", "status IN ('completed', 'stopped')")


def downgrade() -> None:
    op.execute("UPDATE messages SET status = 'completed' WHERE status = 'stopped'")
    op.drop_constraint("messages_status_check", "messages", type_="check")
    op.create_check_constraint("messages_status_check", "messages", "status IN ('completed')")
