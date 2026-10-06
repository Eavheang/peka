from pydantic import BaseModel, Field

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
