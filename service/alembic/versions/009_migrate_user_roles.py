"""migrate user roles to admin, senior, and staff

Revision ID: 009_migrate_user_roles
Revises: 008_create_knowledge_chunks
"""
from typing import Sequence, Union

from alembic import op


revision: str = "009_migrate_user_roles"
down_revision: Union[str, None] = "008_create_knowledge_chunks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("users_role_check", "users", type_="check")
    op.create_check_constraint(
        "users_role_check", "users", "role IN ('admin', 'member', 'staff')"
    )
    op.execute("UPDATE users SET role = 'staff' WHERE role = 'member'")
    op.drop_constraint("users_role_check", "users", type_="check")
    op.create_check_constraint(
        "users_role_check", "users", "role IN ('admin', 'senior', 'staff')"
    )
    op.alter_column("users", "role", server_default="staff")


def downgrade() -> None:
    op.drop_constraint("users_role_check", "users", type_="check")
    op.create_check_constraint(
        "users_role_check", "users", "role IN ('admin', 'member', 'senior', 'staff')"
    )
    op.execute("UPDATE users SET role = 'member' WHERE role IN ('senior', 'staff')")
    op.drop_constraint("users_role_check", "users", type_="check")
    op.create_check_constraint("users_role_check", "users", "role IN ('member', 'admin')")
    op.alter_column("users", "role", server_default="member")
