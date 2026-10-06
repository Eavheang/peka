import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse

from app.auth.routes import authenticated
from app.config import settings
from app.files.schemas import FileResponse
from app.files.service import DuplicateFileError, FileTooLargeError
from app.google_drive.schemas import ConnectResponse, DriveImportRequest, PickerConfig
from app.google_drive.service import (
    GoogleDriveNotConfiguredError,
    GoogleDriveNotConnectedError,
    GoogleDriveRequestError,
    authorization_url,
    complete_connection,
    import_files,
    picker_config,
)

router = APIRouter(prefix="/integrations/google", tags=["google-drive"])


@router.get("/connect", response_model=ConnectResponse)
def connect(user: dict = Depends(authenticated)) -> dict:
    try:
        return {"url": authorization_url(user["id"])}
    except GoogleDriveNotConfiguredError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None


@router.get("/callback", include_in_schema=False)
def callback(code: str | None = None, state: str | None = None) -> RedirectResponse:
    result = "error"
    if code and state:
        try:
            complete_connection(code, state)
            result = "connected"
        except (GoogleDriveNotConfiguredError, GoogleDriveRequestError, jwt.PyJWTError, ValueError):
            pass
    return RedirectResponse(f"{settings.app_base_url}/workspace/knowledge?google_drive={result}")


@router.get("/picker", response_model=PickerConfig)
def get_picker_config(user: dict = Depends(authenticated)) -> dict:
    try:
        return picker_config(user["id"])
    except GoogleDriveNotConfiguredError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    except GoogleDriveNotConnectedError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except GoogleDriveRequestError as error:
        raise HTTPException(status_code=502, detail=str(error)) from None


@router.post("/files", response_model=list[FileResponse], status_code=status.HTTP_201_CREATED)
def import_drive_files(payload: DriveImportRequest, user: dict = Depends(authenticated)) -> list[dict]:
    if user["role"] != "admin" and any(file.access_level == "confidential" for file in payload.files):
        raise HTTPException(status_code=403, detail="Only admins can upload confidential files")
    try:
        return import_files(user["id"], [(file.id, file.access_level) for file in payload.files])
    except GoogleDriveNotConfiguredError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    except GoogleDriveNotConnectedError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except GoogleDriveRequestError as error:
        raise HTTPException(status_code=502, detail=str(error)) from None
    except FileTooLargeError as error:
        raise HTTPException(status_code=413, detail=str(error)) from None
    except DuplicateFileError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except ValueError as error:
        raise HTTPException(status_code=415, detail=str(error)) from None
