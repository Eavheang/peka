from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StoredFile(Base):
    __tablename__ = "files"
    __table_args__ = (
        CheckConstraint("access_level IN ('general', 'confidential')", name="files_access_level_check"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    content_type: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(Text, unique=True)
    author_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    access_level: Mapped[str] = mapped_column(Text, nullable=False, server_default="general")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
