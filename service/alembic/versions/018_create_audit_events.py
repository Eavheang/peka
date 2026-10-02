"""create audit events

Revision ID: 018_create_audit_events
Revises: 017_create_invitations
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "018_create_audit_events"
down_revision: Union[str, None] = "017_create_invitations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("type IN ('sync', 'query', 'system')", name="audit_events_type_check"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "CREATE INDEX audit_events_type_created_at_idx ON audit_events (type, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX audit_events_created_at_idx ON audit_events (created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS audit_events_created_at_idx")
    op.execute("DROP INDEX IF EXISTS audit_events_type_created_at_idx")
    op.drop_table("audit_events")
