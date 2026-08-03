"""create OKF conversion jobs

Revision ID: 007_create_okf_jobs
Revises: 006_unique_file_sha256
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007_create_okf_jobs"
down_revision: Union[str, None] = "006_unique_file_sha256"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "okf_jobs",
        sa.Column("file_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=10), server_default="queued", nullable=False),
        sa.Column("attempts", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed')",
            name="okf_jobs_status_check",
        ),
        sa.CheckConstraint("attempts BETWEEN 0 AND 3", name="okf_jobs_attempts_check"),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("file_id"),
    )
    # Files created before queue support already completed synchronous conversion.
    op.execute("INSERT INTO okf_jobs (file_id, status) SELECT id, 'completed' FROM files")


def downgrade() -> None:
    op.drop_table("okf_jobs")
