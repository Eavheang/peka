from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse as DownloadResponse

from app.auth.routes import admin_only, authenticated
from app.engine.search.service import access_levels_for_role

from app.files.schemas import AccessLevel, AccessLevelUpdate, FileResponse, IndexStatusResponse
from app.files import service as files_service
from app.files.service import (
    DuplicateFileError,
    FileTooLargeError,
    IndexJobStateError,
    delete_file,
    find_file,
    list_files,
    retry_indexing,
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


@router.post("/{file_id}/retry-indexing", response_model=FileResponse)
def retry_file_indexing(file_id: UUID, user: dict = Depends(authenticated)) -> dict:
    try:
        record = retry_indexing(file_id, user["id"], user["role"] == "admin")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Only file author or admin can retry this job") from None
    except IndexJobStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    return record


@router.get("/{file_id}/index-status", response_model=IndexStatusResponse)
def get_index_status(file_id: UUID, user: dict = Depends(authenticated)) -> dict:
    record = files_service.get_index_status(file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    return {
        "file_id": str(record["id"]),
        "index_status": record["index_status"],
        "index_attempts": record["index_attempts"],
        "index_error": record["index_error"],
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
    file_id: UUID, payload: AccessLevelUpdate, _: dict = Depends(admin_only)
) -> dict:
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
