import json
from itertools import count
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from fastapi import UploadFile
from psycopg.errors import UniqueViolation

from app.config import settings
from app.engine.okf.job_repository import okf_jobs_repository
from app.engine.source_extractor import extract_file, source_id_for
from app.files.repository import files_repository


class DuplicateFileError(ValueError):
    pass


class FileTooLargeError(ValueError):
    pass

class OKFJobStateError(ValueError):
    pass

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
    records: list[tuple[str, str | None, str]] = []
    seen_hashes: set[str] = set()

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
                digest = sha256()
                size = 0
                chunk = upload.file.read(1024 * 1024)
                while chunk:
                    size += len(chunk)
                    if size > settings.max_upload_bytes:
                        raise FileTooLargeError(
                            f"{name} exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB limit"
                        )
                    digest.update(chunk)
                    output.write(chunk)
                    chunk = upload.file.read(1024 * 1024)
            file_sha256 = digest.hexdigest()
            if file_sha256 in seen_hashes or files_repository.exists_by_sha256(file_sha256):
                raise DuplicateFileError("A file with identical content already exists")
            seen_hashes.add(file_sha256)
            relative_path = destination.relative_to(storage_root).as_posix()
            try:
                extraction = extract_file(destination, content_hash=file_sha256)
            except Exception as error:
                raise ValueError(f"Unable to extract file: {name}") from error
            extracted = storage_root / "extracted" / f"{extraction['source_id']}.json"
            saved_paths.append(extracted)
            extracted.parent.mkdir(parents=True, exist_ok=True)
            extracted.write_text(json.dumps(extraction, indent=2) + "\n", encoding="utf-8")
            records.append((relative_path, upload.content_type, file_sha256))

        try:
            return files_repository.create_many(records, author_id)
        except UniqueViolation as error:
            raise DuplicateFileError("A file with identical content already exists") from error
    except Exception:
        for path in saved_paths:
            path.unlink(missing_ok=True)
        raise


def list_files() -> list[dict]:
    return files_repository.list_all()


def retry_okf(file_id: UUID, user_id: UUID, is_admin: bool = False) -> dict | None:
    record = files_repository.find_by_id(file_id)
    if record is None:
        return None
    if record["author_id"] != user_id and not is_admin:
        raise PermissionError
    if not okf_jobs_repository.retry_failed(file_id):
        raise OKFJobStateError("Only failed OKF jobs can be retried")
    return files_repository.find_by_id(file_id)


def get_okf_status(file_id: UUID) -> dict | None:
    return files_repository.find_by_id(file_id)


def set_access_level(file_id: UUID, access_level: str) -> dict | None:
    if not files_repository.update_access_level(file_id, access_level):
        return None
    return files_repository.find_by_id(file_id)


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
        (storage_root / "extracted" / f"{source_id_for(path)}.json").unlink(missing_ok=True)
    return True


def _create_destination(directory: Path, name: str) -> tuple[Path, BinaryIO]:
    source = Path(name)
    for suffix in count():
        candidate = directory / (name if suffix == 0 else f"{source.stem}_{suffix}{source.suffix}")
        try:
            return candidate, candidate.open("xb")
        except FileExistsError:
            continue
    raise RuntimeError("Unable to create file destination")
