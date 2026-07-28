from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse as DownloadResponse

from app.auth.routes import authenticated
from app.files.schemas import FileResponse
from app.files.service import DuplicateFileError, delete_file, find_file, list_files, store_files

router = APIRouter(prefix="/files", tags=["files"])


@router.post("", response_model=list[FileResponse], status_code=status.HTTP_201_CREATED)
def upload_files(
    files: Annotated[list[UploadFile], File()],
    user: dict = Depends(authenticated),
) -> list[dict]:
    try:
        return store_files(files, user["id"])
    except DuplicateFileError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except ValueError as error:
        raise HTTPException(status_code=415, detail=str(error)) from None


@router.get("", response_model=list[FileResponse])
def get_files(_: dict = Depends(authenticated)) -> list[dict]:
    return list_files()


@router.get("/{file_id}")
def download_file(file_id: UUID, _: dict = Depends(authenticated)) -> DownloadResponse:
    result = find_file(file_id)
    if result is None:
        raise HTTPException(status_code=404, detail="File not found")
    record, path = result
    return DownloadResponse(path, media_type=record["content_type"], filename=path.name)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_file(file_id: UUID, user: dict = Depends(authenticated)) -> Response:
    try:
        deleted = delete_file(file_id, user["id"], user["role"] == "admin")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Only file author or admin can delete this file") from None
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")
    return Response(status_code=204)
