"""store search vectors and file centroids, and index chunks for keyword and vector search

Chunks hold a copy of their file's path because a generated column cannot read another
table. Paths never change after upload, so the copy cannot go stale.

HNSW settings and the reasoning are in eval/results-perf/2026-11-07-search-indexes/notes.md.

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
    # The rewrites below block search and indexing, so give up rather than queue behind other work.
    op.execute("SET LOCAL lock_timeout = '10s'")
    op.execute("ALTER TABLE knowledge_chunks ADD COLUMN file_path text")
    op.execute("UPDATE knowledge_chunks kc SET file_path = f.path FROM files f WHERE f.id = kc.file_id")
    op.execute("ALTER TABLE knowledge_chunks ALTER COLUMN file_path SET NOT NULL")
    op.execute(
        "ALTER TABLE knowledge_chunks ADD COLUMN search_words tsvector GENERATED ALWAYS AS "
        "(to_tsvector('english'::regconfig, regexp_replace(file_path, '[^[:alnum:]]+', ' ', 'g')"
        " || ' ' || heading || ' ' || content)) STORED"
    )
    op.execute("CREATE INDEX knowledge_chunks_search_words_idx ON knowledge_chunks USING gin (search_words)")
    op.execute(
        "CREATE INDEX knowledge_chunks_embedding_idx ON knowledge_chunks "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 32, ef_construction = 200)"
    )
    op.execute("ALTER TABLE chunk_sets ADD COLUMN centroid vector")
    op.execute(
        "UPDATE chunk_sets cs SET centroid = "
        "(SELECT avg(kc.embedding) FROM knowledge_chunks kc WHERE kc.chunk_set_id = cs.id)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE chunk_sets DROP COLUMN centroid")
    op.execute("DROP INDEX knowledge_chunks_embedding_idx")
    op.execute("DROP INDEX knowledge_chunks_search_words_idx")
    op.execute("ALTER TABLE knowledge_chunks DROP COLUMN search_words")
    op.execute("ALTER TABLE knowledge_chunks DROP COLUMN file_path")
