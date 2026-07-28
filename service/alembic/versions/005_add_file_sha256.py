"""add SHA-256 digest to files

Revision ID: 005_add_file_sha256
Revises: 004_add_user_activation
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005_add_file_sha256"
down_revision: Union[str, None] = "004_add_user_activation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("files", sa.Column("sha256", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("files", "sha256")
