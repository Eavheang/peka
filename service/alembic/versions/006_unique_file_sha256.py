"""make file content hashes unique

Revision ID: 006_unique_file_sha256
Revises: 005_add_file_sha256
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006_unique_file_sha256"
down_revision: Union[str, None] = "005_add_file_sha256"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep oldest metadata row so existing duplicate uploads do not block migration.
    op.execute(sa.text("""
        DELETE FROM files newer
        USING files older
        WHERE newer.sha256 IS NOT NULL
          AND newer.sha256 = older.sha256
          AND (newer.created_at, newer.id) > (older.created_at, older.id)
    """))
    op.create_unique_constraint("files_sha256_key", "files", ["sha256"])


def downgrade() -> None:
    op.drop_constraint("files_sha256_key", "files", type_="unique")
