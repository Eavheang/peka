"""record which chunker built each chunk set, and index message citations

Existing sets get version 0, so the index worker re-indexes them with the current chunker.

Revision ID: 023_add_chunker_version
Revises: 022_rename_okf_jobs
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "023_add_chunker_version"
down_revision: Union[str, None] = "022_rename_okf_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chunk_sets", sa.Column("chunker_version", sa.Integer(), nullable=False, server_default="0"))
    # A re-index keeps the chunks saved answers cite, looked up by containment on the citations.
    op.execute("CREATE INDEX messages_citations_idx ON messages USING gin (citations jsonb_path_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX messages_citations_idx")
    op.drop_column("chunk_sets", "chunker_version")
