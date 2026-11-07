"""store search vectors and index chunks for keyword search

The file path stays searchable through its own column because a generated column
cannot read another table. Paths never change after upload.

There is no HNSW index on embeddings on purpose. The query can use one, but on 50,000
chunks with many near-duplicates, as format copies produce, it found about 60% of the
true top 80 (under 70% even at ef_search 1000, and none at all for some questions).
Exact search took 150 to 190 ms on the same data, so accuracy is not worth trading yet.
Method and figures: eval/results-perf/2026-11-07-search-indexes/notes.md.

Revision ID: 021_add_search_indexes
Revises: 020_allow_stopped_messages
"""
from typing import Sequence, Union

from alembic import op


revision: str = "021_add_search_indexes"
down_revision: Union[str, None] = "020_allow_stopped_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE knowledge_chunks ADD COLUMN search_words tsvector GENERATED ALWAYS AS "
        "(to_tsvector('english'::regconfig, heading || ' ' || content)) STORED"
    )
    op.execute(
        "ALTER TABLE files ADD COLUMN path_words tsvector GENERATED ALWAYS AS "
        "(to_tsvector('english'::regconfig, regexp_replace(path, '[^[:alnum:]]+', ' ', 'g'))) STORED"
    )
    op.execute("CREATE INDEX knowledge_chunks_search_words_idx ON knowledge_chunks USING gin (search_words)")


def downgrade() -> None:
    op.execute("DROP INDEX knowledge_chunks_search_words_idx")
    op.execute("ALTER TABLE files DROP COLUMN path_words")
    op.execute("ALTER TABLE knowledge_chunks DROP COLUMN search_words")
