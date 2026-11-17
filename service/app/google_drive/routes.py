from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse

from app import connectivity
from app.auth.routes import admin_only, authenticated
from app.config import settings
from app.files.schemas import FileResponse
from app.files.service import DuplicateFileError, FileTooLargeError
from app.google_drive.schemas import (
    ConnectResponse,
    DriveImportRequest,
    DriveSyncSettings,
    DriveSyncUpdate,
    PickerConfig,
)
from app.google_drive.service import (
    SCOPE,
    SYNC_SCOPE,
    GoogleDriveNotConfiguredError,
    GoogleDriveNotConnectedError,
    GoogleDriveRequestError,
    authorization_url,
    complete_connection,
    import_files,
    picker_config,
    return_page,
    request_sync_run,
    save_sync_settings,
    stop_sync,
    sync_settings,
)

router = APIRouter(prefix="/integrations/google", tags=["google-drive"])


def _require_internet() -> None:
    if not connectivity.is_online():
        raise HTTPException(status_code=503, detail="Google Drive needs an internet connection. PEKA is offline.")


def _connect(user_id: UUID, scope: str, return_page: str) -> dict:
    try:
        return {"url": authorization_url(user_id, scope, return_page)}
    except GoogleDriveNotConfiguredError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None


def _picker(user_id: UUID, scope: str | None = None) -> dict:
    try:
        return picker_config(user_id, scope)
    except GoogleDriveNotConfiguredError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    except GoogleDriveNotConnectedError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except GoogleDriveRequestError as error:
        raise HTTPException(status_code=502, detail=str(error)) from None


@router.get("/connect", response_model=ConnectResponse, dependencies=[Depends(_require_internet)])
def connect(user: dict = Depends(authenticated)) -> dict:
    return _connect(user["id"], SCOPE, "knowledge")


@router.get("/callback", include_in_schema=False)
def callback(code: str | None = None, state: str | None = None) -> RedirectResponse:
    result, page = "error", (state and return_page(state)) or "knowledge"
    if code and state:
        try:
            complete_connection(code, state)
            result = "connected"
        except (GoogleDriveNotConfiguredError, GoogleDriveRequestError, jwt.PyJWTError, ValueError):
            pass
    return RedirectResponse(f"{settings.app_base_url}/workspace/{page}?google_drive={result}")


@router.get("/picker", response_model=PickerConfig, dependencies=[Depends(_require_internet)])
def get_picker_config(user: dict = Depends(authenticated)) -> dict:
    return _picker(user["id"])


@router.post("/files", response_model=list[FileResponse], status_code=status.HTTP_201_CREATED, dependencies=[Depends(_require_internet)])
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


@router.get("/sync/connect", response_model=ConnectResponse, dependencies=[Depends(_require_internet)])
def connect_for_sync(user: dict = Depends(admin_only)) -> dict:
    """Like /connect, plus read access to the whole Drive, which folder sync needs."""
    return _connect(user["id"], SYNC_SCOPE, "admin/settings")


@router.get("/sync/picker", response_model=PickerConfig, dependencies=[Depends(_require_internet)])
def get_sync_picker_config(user: dict = Depends(admin_only)) -> dict:
    """Picker for the sync folder; 409 until the admin's connection can read the whole Drive."""
    return _picker(user["id"], SYNC_SCOPE)


@router.get("/sync", response_model=DriveSyncSettings | None)
def get_sync(_: dict = Depends(admin_only)) -> dict | None:
    return sync_settings()


@router.put("/sync", response_model=DriveSyncSettings)
def put_sync(payload: DriveSyncUpdate, user: dict = Depends(admin_only)) -> dict:
    """Makes this admin the owner. A different folder starts over: files already in it count as existing."""
    return save_sync_settings(user["id"], payload.folder_id, payload.folder_name, payload.access_level,
                              payload.timezone, payload.sync_time)


@router.post("/sync/run", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(_require_internet)])
def run_sync(_: dict = Depends(admin_only)) -> Response:
    """Sync now: the index worker starts the run within a minute."""
    if not request_sync_run():
        raise HTTPException(status_code=404, detail="Folder sync is not set up")
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.delete("/sync", status_code=status.HTTP_204_NO_CONTENT)
def delete_sync(_: dict = Depends(admin_only)) -> Response:
    """Stop syncing. Files already synced stay in PEKA."""
    stop_sync()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
