from datetime import date, datetime, time
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, SmallInteger, Text, Time, text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class GoogleDriveConnection(Base):
    __tablename__ = "google_drive_connections"

    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # Fernet-encrypted: an admin's token reads their whole Drive for folder sync.
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class GoogleDriveSync(Base):
    """The one Drive folder the index worker mirrors. Single row: one folder is the source of truth."""

    __tablename__ = "google_drive_sync"
    __table_args__ = (
        CheckConstraint("id = 1", name="google_drive_sync_single_row_check"),
        CheckConstraint("access_level IN ('general', 'confidential')", name="google_drive_sync_access_level_check"),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, server_default=text("1"))
    # The admin whose Drive connection reads the folder.
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    folder_id: Mapped[str] = mapped_column(Text, nullable=False)
    folder_name: Mapped[str] = mapped_column(Text, nullable=False)
    access_level: Mapped[str] = mapped_column(Text, nullable=False, server_default="general")
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    sync_time: Mapped[time] = mapped_column(Time, nullable=False, server_default=text("'00:00'"))
    last_run_on: Mapped[date | None] = mapped_column(Date)
    run_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_result: Mapped[str | None] = mapped_column(Text)


class GoogleDriveSyncedFile(Base):
    __tablename__ = "google_drive_synced_files"

    drive_file_id: Mapped[str] = mapped_column(Text, primary_key=True)
    sync_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("google_drive_sync.id", ondelete="CASCADE"), nullable=False, server_default=text("1")
    )
    # NULL: skipped, or deleted in PEKA. An edit in Drive imports it.
    file_id: Mapped[UUID | None] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"))
    modified_time: Mapped[str] = mapped_column(Text, nullable=False)
