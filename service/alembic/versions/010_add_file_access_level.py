"""add access level to files

Revision ID: 010_add_file_access_level
Revises: 009_migrate_user_roles
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "010_add_file_access_level"
down_revision: Union[str, None] = "009_migrate_user_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "files",
        sa.Column("access_level", sa.Text(), nullable=False, server_default="general"),
    )
    op.create_check_constraint(
        "files_access_level_check", "files", "access_level IN ('general', 'confidential')"
    )


def downgrade() -> None:
    op.drop_constraint("files_access_level_check", "files", type_="check")
    op.drop_column("files", "access_level")
