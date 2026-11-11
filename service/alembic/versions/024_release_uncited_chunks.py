"""delete kept chunks once no saved message cites them

A re-index keeps superseded chunks that saved answers cite. When those messages go (regenerate, conversation or
user deletion, including cascades), this trigger deletes the kept chunks they alone cited.

Revision ID: 024_release_uncited_chunks
Revises: 023_add_chunker_version
"""
from typing import Sequence, Union

from alembic import op


revision: str = "024_release_uncited_chunks"
down_revision: Union[str, None] = "023_add_chunker_version"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION release_uncited_chunks() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            DELETE FROM knowledge_chunks kc USING chunk_sets cs
            WHERE kc.id IN (
                -- Guarded so one malformed old row can't make every message delete fail.
                SELECT CASE WHEN citation->>'chunk_id' ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                            THEN (citation->>'chunk_id')::uuid END
                FROM removed, jsonb_array_elements(
                    CASE WHEN jsonb_typeof(removed.citations) = 'array' THEN removed.citations ELSE '[]'::jsonb END
                ) citation
            )
            AND cs.id = kc.chunk_set_id AND cs.status = 'superseded'
            AND NOT EXISTS (
                SELECT 1 FROM messages
                WHERE citations @> jsonb_build_array(jsonb_build_object('chunk_id', kc.id::text))
            );
            RETURN NULL;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER messages_release_uncited_chunks AFTER DELETE ON messages "
        "REFERENCING OLD TABLE AS removed FOR EACH STATEMENT EXECUTE FUNCTION release_uncited_chunks()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER messages_release_uncited_chunks ON messages")
    op.execute("DROP FUNCTION release_uncited_chunks()")
