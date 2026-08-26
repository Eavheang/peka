"""switch knowledge embeddings to BGE small

Revision ID: 012_resize_embeddings
Revises: 011_create_chunk_sets
"""
from typing import Sequence, Union

from alembic import op

revision: str = "012_resize_embeddings"
down_revision: Union[str, None] = "011_create_chunk_sets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing vectors cannot be reused after changing dimensions; source files remain available for reindexing.
    op.execute("DELETE FROM knowledge_chunks")
    op.execute("DELETE FROM chunk_sets")
    op.execute(
        "ALTER TABLE knowledge_chunks "
        "ALTER COLUMN embedding TYPE vector(384)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE knowledge_chunks "
        "ALTER COLUMN embedding TYPE vector(1024)"
    )
