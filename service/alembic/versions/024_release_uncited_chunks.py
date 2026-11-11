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
                SELECT (citation->>'chunk_id')::uuid
                FROM removed, jsonb_array_elements(removed.citations) citation
                WHERE citation->>'chunk_id' IS NOT NULL
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
