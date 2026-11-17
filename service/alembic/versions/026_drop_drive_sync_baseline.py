"""import files already in the synced Drive folder

The first run after picking a folder recorded the files already in it without importing them; now it imports them.
Rows with no PEKA file are forgotten and a run queued, so those files import now. This can't tell them from files
deleted in PEKA, which come back; skipped files are skipped again.

Revision ID: 026_drop_drive_sync_baseline
Revises: 025_create_google_drive_sync
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "026_drop_drive_sync_baseline"
down_revision: Union[str, None] = "025_create_google_drive_sync"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM google_drive_synced_files WHERE file_id IS NULL")
    op.execute("UPDATE google_drive_sync SET run_requested = true")
    op.drop_column("google_drive_sync", "needs_baseline")


def downgrade() -> None:
    # false for the existing row, whose files are already mapped; true again for folders picked after.
    op.add_column(
        "google_drive_sync",
        sa.Column("needs_baseline", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.alter_column("google_drive_sync", "needs_baseline", server_default=sa.text("true"))
