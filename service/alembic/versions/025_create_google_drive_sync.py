"""create google drive folder sync, encrypt drive tokens

One workspace-wide folder an admin picks. The index worker imports new and edited files from its tree at a
set local time each day and removes files deleted from it. Existing Drive tokens were stored in plaintext;
they are cleared so every user reconnects once and gets an encrypted token.

Revision ID: 025_create_google_drive_sync
Revises: 024_release_uncited_chunks
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "025_create_google_drive_sync"
down_revision: Union[str, None] = "024_release_uncited_chunks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "google_drive_sync",
        sa.Column("id", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("folder_id", sa.Text(), nullable=False),
        sa.Column("folder_name", sa.Text(), nullable=False),
        sa.Column("access_level", sa.Text(), server_default="general", nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("sync_time", sa.Time(), server_default=sa.text("'00:00'"), nullable=False),
        sa.Column("last_run_on", sa.Date(), nullable=True),
        sa.Column("run_requested", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("needs_baseline", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_result", sa.Text(), nullable=True),
        sa.CheckConstraint("id = 1", name="google_drive_sync_single_row_check"),
        sa.CheckConstraint("access_level IN ('general', 'confidential')", name="google_drive_sync_access_level_check"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "google_drive_synced_files",
        sa.Column("drive_file_id", sa.Text(), nullable=False),
        sa.Column("sync_id", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        # NULL: present when the folder was picked, skipped, or deleted in PEKA. An edit in Drive imports it.
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("modified_time", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["sync_id"], ["google_drive_sync.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("drive_file_id"),
    )
    op.execute("DELETE FROM google_drive_connections")


def downgrade() -> None:
    op.drop_table("google_drive_synced_files")
    op.drop_table("google_drive_sync")
