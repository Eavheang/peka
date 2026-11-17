from datetime import datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator

from app.files.schemas import AccessLevel


class ConnectResponse(BaseModel):
    url: str


class PickerConfig(BaseModel):
    access_token: str
    api_key: str
    app_id: str


class DriveFileSelection(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    access_level: AccessLevel = "general"


class DriveImportRequest(BaseModel):
    files: list[DriveFileSelection] = Field(min_length=1, max_length=50)


class DriveSyncUpdate(BaseModel):
    # Drive IDs are URL-safe base64; the pattern also keeps quotes out of the Drive search query.
    folder_id: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_-]+$")
    folder_name: str = Field(min_length=1, max_length=500)
    access_level: AccessLevel = "general"
    timezone: str = Field(min_length=1, max_length=100)
    sync_time: time = time(0, 0)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Must be an IANA time zone such as Asia/Phnom_Penh") from None
        return value


class DriveSyncSettings(DriveSyncUpdate):
    owner_email: str
    run_requested: bool
    last_synced_at: datetime | None
    last_result: str | None
