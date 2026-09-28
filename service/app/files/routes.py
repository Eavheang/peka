from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse as DownloadResponse

from app.auth.routes import authenticated
from app.engine.search.service import access_levels_for_role

from app.files.schemas import AccessLevel, AccessLevelUpdate, FileResponse, OKFStatusResponse
from app.files import service as files_service
from app.files.service import (
    DuplicateFileError,
    FileTooLargeError,
    OKFJobStateError,
    delete_file,
    find_file,
    list_files,
    retry_okf,
    set_access_level,
    store_files,
)

router = APIRouter(prefix="/files", tags=["files"])


@router.post("", response_model=list[FileResponse], status_code=status.HTTP_201_CREATED)
def upload_files(
    files: Annotated[list[UploadFile], File()],
    access_levels: Annotated[list[AccessLevel] | None, Form()] = None,
    user: dict = Depends(authenticated),
) -> list[dict]:
    levels = access_levels if access_levels is not None else ["general"] * len(files)
    if len(levels) != len(files):
        raise HTTPException(status_code=422, detail="Each uploaded file must have an access level")
    if user["role"] != "admin" and "confidential" in levels:
        raise HTTPException(status_code=403, detail="Only admins can upload confidential files")
    try:
        return store_files(files, user["id"], levels)
    except FileTooLargeError as error:
        raise HTTPException(status_code=413, detail=str(error)) from None
    except DuplicateFileError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except ValueError as error:
        raise HTTPException(status_code=415, detail=str(error)) from None


@router.get("", response_model=list[FileResponse])
def get_files(user: dict = Depends(authenticated)) -> list[dict]:
    return list_files(access_levels_for_role(user["role"]))


@router.post("/{file_id}/retry-okf", response_model=FileResponse)
def retry_file_okf(file_id: UUID, user: dict = Depends(authenticated)) -> dict:
    try:
        record = retry_okf(file_id, user["id"], user["role"] == "admin")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Only file author or admin can retry this job") from None
    except OKFJobStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    return record


@router.get("/{file_id}/okf-status", response_model=OKFStatusResponse)
def get_okf_status(file_id: UUID, user: dict = Depends(authenticated)) -> dict:
    record = files_service.get_okf_status(file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    return {
        "file_id": str(record["id"]),
        "okf_status": record["okf_status"],
        "okf_attempts": record["okf_attempts"],
        "okf_error": record["okf_error"],
    }


@router.get("/{file_id}")
def download_file(file_id: UUID, user: dict = Depends(authenticated)) -> DownloadResponse:
    result = find_file(file_id, access_levels_for_role(user["role"]))
    if result is None:
        raise HTTPException(status_code=404, detail="File not found")
    record, path = result
    return DownloadResponse(path, media_type=record["content_type"], filename=path.name)


@router.patch("/{file_id}/access-level", response_model=FileResponse)
def change_file_access_level(
    file_id: UUID, payload: AccessLevelUpdate, user: dict = Depends(authenticated)
) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can change file access level")
    record = set_access_level(file_id, payload.access_level)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    return record


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_file(file_id: UUID, user: dict = Depends(authenticated)) -> Response:
    try:
        deleted = delete_file(file_id, user["id"], user["role"] == "admin")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Only file author or admin can delete this file") from None
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")
    return Response(status_code=204)
