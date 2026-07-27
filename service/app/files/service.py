from itertools import count
from pathlib import Path
from shutil import copyfileobj
from uuid import UUID

from fastapi import UploadFile

from app.config import settings
from app.files.repository import files_repository

FILE_CATEGORIES = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".pptx": "pptx",
    ".xlsx": "xlsx",
    ".md": "others",
    ".txt": "others",
}


def store_files(uploads: list[UploadFile], author_id: UUID) -> list[dict]:
    storage_root = settings.file_storage_dir.resolve()
    saved_paths: list[Path] = []
    records: list[tuple[str, str | None]] = []

    try:
        for upload in uploads:
            name = Path((upload.filename or "").replace("\\", "/")).name.strip()
            category = FILE_CATEGORIES.get(Path(name).suffix.lower())
            if not name or category is None:
                raise ValueError("Only PDF, DOCX, PPTX, XLSX, MD, and TXT files are supported")

            directory = storage_root / category
            directory.mkdir(parents=True, exist_ok=True)
            destination, output = _create_destination(directory, name)
            saved_paths.append(destination)
            with output:
                copyfileobj(upload.file, output)
            records.append((destination.relative_to(storage_root).as_posix(), upload.content_type))

        return files_repository.create_many(records, author_id)
    except Exception:
        for path in saved_paths:
            path.unlink(missing_ok=True)
        raise


def list_files() -> list[dict]:
    return files_repository.list_all()


def find_file(file_id: UUID) -> tuple[dict, Path] | None:
    record = files_repository.find_by_id(file_id)
    if record is None:
        return None
    storage_root = settings.file_storage_dir.resolve()
    path = (storage_root / record["path"]).resolve()
    if not path.is_relative_to(storage_root) or not path.is_file():
        return None
    return record, path


def delete_file(file_id: UUID, user_id: UUID, is_admin: bool = False) -> bool:
    record = files_repository.find_by_id(file_id)
    if record is None:
        return False
    if record["author_id"] != user_id and not is_admin:
        raise PermissionError

    storage_root = settings.file_storage_dir.resolve()
    path = (storage_root / record["path"]).resolve()
    files_repository.delete(file_id)
    if path.is_relative_to(storage_root):
        path.unlink(missing_ok=True)
    return True


def _create_destination(directory: Path, name: str):
    source = Path(name)
    for suffix in count():
        candidate = directory / (name if suffix == 0 else f"{source.stem}_{suffix}{source.suffix}")
        try:
            return candidate, candidate.open("xb")
        except FileExistsError:
            continue
