"""rename okf_jobs to index_jobs

The table has only tracked indexing since OKF conversion was removed.

Revision ID: 022_rename_okf_jobs
Revises: 021_add_search_indexes
"""
from typing import Sequence, Union

from alembic import op


revision: str = "022_rename_okf_jobs"
down_revision: Union[str, None] = "021_add_search_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINTS = ("pkey", "file_id_fkey", "status_check", "attempts_check")


def _rename(old: str, new: str) -> None:
    op.execute(f"ALTER TABLE {old}_jobs RENAME TO {new}_jobs")
    for suffix in _CONSTRAINTS:
        op.execute(f"ALTER TABLE {new}_jobs RENAME CONSTRAINT {old}_jobs_{suffix} TO {new}_jobs_{suffix}")


def upgrade() -> None:
    _rename("okf", "index")


def downgrade() -> None:
    _rename("index", "okf")
