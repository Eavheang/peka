"""create chunk sets and link knowledge chunks

Revision ID: 011_create_chunk_sets
Revises: 010_add_file_access_level
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID


revision: str = "011_create_chunk_sets"
down_revision: Union[str, None] = "010_add_file_access_level"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chunk_sets",
        sa.Column("id", PostgresUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "file_id",
            PostgresUUID(as_uuid=True),
            sa.ForeignKey("files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="building"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("status IN ('building', 'active', 'superseded')", name="chunk_sets_status_check"),
    )
    op.create_index("chunk_sets_file_id_idx", "chunk_sets", ["file_id"])
    op.add_column(
        "knowledge_chunks",
        sa.Column(
            "chunk_set_id",
            PostgresUUID(as_uuid=True),
            sa.ForeignKey("chunk_sets.id", ondelete="CASCADE"),
        ),
    )
    # Backfill: one active set per file that already has chunks, owning those rows.
    op.execute(
        "INSERT INTO chunk_sets (file_id, status) "
        "SELECT DISTINCT file_id, 'active' FROM knowledge_chunks"
    )
    op.execute(
        "UPDATE knowledge_chunks kc SET chunk_set_id = cs.id "
        "FROM chunk_sets cs WHERE cs.file_id = kc.file_id AND kc.chunk_set_id IS NULL"
    )


def downgrade() -> None:
    op.drop_column("knowledge_chunks", "chunk_set_id")
    op.drop_table("chunk_sets")
