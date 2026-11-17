import logging
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import cast
from urllib.parse import urlencode
from uuid import UUID

import httpx
import jwt
from fastapi import UploadFile
from starlette.datastructures import Headers

from app import connectivity
from app.audit.service import record_audit_event
from app.config import settings
from app.files.service import FILE_CATEGORIES, FileTooLargeError, delete_file, store_files
from app.google_drive.repository import google_drive_repository

logger = logging.getLogger(__name__)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
FILES_URL = "https://www.googleapis.com/drive/v3/files"
SCOPE = "https://www.googleapis.com/auth/drive.file"
# Folder sync lists files nobody picked, which drive.file cannot see. Only the admin who sets up sync grants it.
SYNC_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

# Native Google files have no binary content; export them to the matching Office format.
EXPORTS = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"),
}


class GoogleDriveError(RuntimeError):
    """A Google Drive problem whose message is safe to show to users."""


class GoogleDriveNotConfiguredError(GoogleDriveError):
    pass


class GoogleDriveNotConnectedError(GoogleDriveError):
    pass


class GoogleDriveRequestError(GoogleDriveError):
    pass


def google_drive_configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret
                and settings.google_api_key and settings.google_app_id)


def _client_credentials() -> tuple[str, str]:
    if not google_drive_configured():
        raise GoogleDriveNotConfiguredError("Google Drive is not configured")
    return settings.google_client_id, settings.google_client_secret.get_secret_value()


def authorization_url(user_id: UUID, scope: str, return_page: str) -> str:
    client_id, _ = _client_credentials()
    now = datetime.now(timezone.utc)
    # Signed state ties the callback to the user who started it, without a server-side session.
    state = jwt.encode(
        {"sub": str(user_id), "typ": "google_drive_state", "page": return_page, "iss": settings.jwt_issuer,
         "aud": settings.jwt_audience, "iat": now, "exp": now + timedelta(minutes=10)},
        settings.jwt_secret_key.get_secret_value(), algorithm="HS256",
    )
    return f"{AUTH_URL}?" + urlencode({
        "client_id": client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",  # always return a refresh token, even on reconnect
        "include_granted_scopes": "true",
        "state": state,
    })


def _decode_state(state: str) -> dict:
    claims = jwt.decode(
        state, settings.jwt_secret_key.get_secret_value(), algorithms=["HS256"],
        issuer=settings.jwt_issuer, audience=settings.jwt_audience,
        options={"require": ["sub", "typ", "exp"]},
    )
    if claims["typ"] != "google_drive_state":
        raise jwt.InvalidTokenError("invalid state")
    return claims


def return_page(state: str) -> str | None:
    """The page that started the connection, so a refused consent also lands back there."""
    try:
        return _decode_state(state).get("page")
    except jwt.PyJWTError:
        return None


def complete_connection(code: str, state: str) -> None:
    client_id, client_secret = _client_credentials()
    claims = _decode_state(state)
    response = httpx.post(TOKEN_URL, data={
        "code": code, "client_id": client_id, "client_secret": client_secret,
        "redirect_uri": settings.google_redirect_uri, "grant_type": "authorization_code",
    }, timeout=30)
    if response.status_code != 200 or "refresh_token" not in response.json():
        raise GoogleDriveRequestError("Google did not return a refresh token")
    google_drive_repository.save_refresh_token(UUID(claims["sub"]), response.json()["refresh_token"])


def access_token(user_id: UUID, scope: str | None = None) -> str:
    client_id, client_secret = _client_credentials()
    refresh_token = google_drive_repository.find_refresh_token(user_id)
    if refresh_token is None:
        raise GoogleDriveNotConnectedError("Google Drive is not connected")
    response = httpx.post(TOKEN_URL, data={
        "client_id": client_id, "client_secret": client_secret,
        "refresh_token": refresh_token, "grant_type": "refresh_token",
    }, timeout=30)
    if response.status_code == 400 and response.json().get("error") == "invalid_grant":
        # Revoked or expired consent: forget it so the user is asked to reconnect.
        google_drive_repository.delete(user_id)
        raise GoogleDriveNotConnectedError("Google Drive access expired; reconnect it")
    if response.status_code != 200:
        raise GoogleDriveRequestError("Unable to refresh Google Drive access")
    if scope and scope not in response.json().get("scope", "").split():
        raise GoogleDriveNotConnectedError("Reconnect Google Drive to allow folder sync")
    return response.json()["access_token"]


def picker_config(user_id: UUID, scope: str | None = None) -> dict:
    return {"access_token": access_token(user_id, scope), "api_key": settings.google_api_key,
            "app_id": settings.google_app_id}


def import_files(user_id: UUID, selections: list[tuple[str, str]]) -> list[dict]:
    token = access_token(user_id)
    uploads: list[UploadFile] = []
    try:
        with httpx.Client(headers={"Authorization": f"Bearer {token}"}, timeout=60) as client:
            for file_id, _ in selections:
                uploads.append(_download(client, file_id))
        return store_files(uploads, user_id, [level for _, level in selections])
    finally:
        for upload in uploads:
            upload.file.close()


def _download(client: httpx.Client, file_id: str, name: str | None = None, mime_type: str | None = None) -> UploadFile:
    if name is None or mime_type is None:
        metadata = client.get(f"{FILES_URL}/{file_id}",
                              params={"fields": "name,mimeType", "supportsAllDrives": "true"})
        if metadata.status_code != 200:
            raise GoogleDriveRequestError("Unable to read a selected Google Drive file")
        name, mime_type = metadata.json()["name"], metadata.json()["mimeType"]

    if mime_type in EXPORTS:
        mime_type, extension = EXPORTS[mime_type]
        if not name.lower().endswith(extension):
            name += extension
        url, params = f"{FILES_URL}/{file_id}/export", {"mimeType": mime_type}
    else:
        url, params = f"{FILES_URL}/{file_id}", {"alt": "media", "supportsAllDrives": "true"}

    output = SpooledTemporaryFile(max_size=1024 * 1024)
    try:
        with client.stream("GET", url, params=params) as response:
            if response.status_code != 200:
                raise GoogleDriveRequestError(f"Unable to download {name} from Google Drive")
            size = 0
            for chunk in response.iter_bytes(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise FileTooLargeError(
                        f"{name} exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB limit"
                    )
                output.write(chunk)
    except Exception:
        output.close()
        raise
    output.seek(0)
    return UploadFile(file=output, filename=name, headers=Headers({"content-type": mime_type}))


def sync_settings() -> dict | None:
    return google_drive_repository.find_sync()


def save_sync_settings(user_id: UUID, folder_id: str, folder_name: str, access_level: str,
                       timezone_name: str, sync_time: time) -> dict:
    google_drive_repository.save_sync(user_id, folder_id, folder_name, access_level, timezone_name, sync_time)
    return cast(dict, google_drive_repository.find_sync())


def request_sync_run() -> bool:
    return google_drive_repository.request_run()


def stop_sync() -> None:
    google_drive_repository.delete_sync()


def sync_folder() -> None:
    """Run the folder sync when it is due. The index worker calls this about once a minute."""
    # Offline: the run stays due and starts once the internet is back.
    if not google_drive_repository.is_due() or not connectivity.is_online():
        return
    job = google_drive_repository.claim_due()
    if job is None:
        return
    event = "drive_sync_failed"
    try:
        if not job["owner_is_admin"]:
            raise GoogleDriveNotConnectedError(
                "the admin who set it up is no longer an active admin. Another admin must save it again")
        token = access_token(job["user_id"], SYNC_SCOPE)
        with httpx.Client(headers={"Authorization": f"Bearer {token}"}, timeout=60) as client:
            current = _list_tree(client, job["folder_id"])
            if job["needs_baseline"]:
                google_drive_repository.save_baseline(
                    job["folder_id"], {file_id: item["modifiedTime"] for file_id, item in current.items()})
                result = f"Folder picked with {len(current)} existing files; new and edited files sync from now on."
            else:
                result = _mirror(client, job, current)
        event = "drive_sync_completed"
    except GoogleDriveError as error:
        logger.warning("Google Drive folder sync failed: %s", error)
        result = f"Sync failed: {error}"
    except Exception:
        logger.exception("Google Drive folder sync failed")
        result = "Sync failed: unexpected error, see the index worker log."
    record_audit_event(event, actor_id=job["user_id"], metadata={"result": result})
    google_drive_repository.finish_run(job["folder_id"], result)


def _list_tree(client: httpx.Client, root_id: str) -> dict[str, dict]:
    """Every file under the folder, subfolders included. Raises unless the whole tree was listed."""
    root = client.get(f"{FILES_URL}/{root_id}", params={"fields": "trashed", "supportsAllDrives": "true"})
    if root.status_code != 200 or root.json().get("trashed"):
        raise GoogleDriveRequestError("The synced folder is gone, in the trash, or no longer shared with you")
    files: dict[str, dict] = {}
    folders = [root_id]
    while folders:
        params = {"q": f"'{folders.pop()}' in parents and trashed = false", "pageSize": 1000,
                  "fields": "nextPageToken,files(id,name,mimeType,modifiedTime,size)",
                  "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
        while True:
            response = client.get(FILES_URL, params=params)
            if response.status_code != 200:
                raise GoogleDriveRequestError("Unable to list the synced Google Drive folder")
            page = response.json()
            for item in page["files"]:
                # Shortcuts are not followed, so a shortcut to a parent cannot loop.
                if item["mimeType"] == FOLDER_MIME_TYPE:
                    folders.append(item["id"])
                else:
                    files[item["id"]] = item
            if "nextPageToken" not in page:
                break
            params["pageToken"] = page["nextPageToken"]
    return files


def _mirror(client: httpx.Client, job: dict, current: dict[str, dict]) -> str:
    known = google_drive_repository.synced_files()
    added = updated = removed = skipped = failed = 0
    # ponytail: one file at a time inside the single worker; uploads wait while a big batch lands.
    for drive_id, item in current.items():
        previous = known.get(drive_id)
        if previous and previous["modified_time"] == item["modifiedTime"]:
            continue
        old_file_id = previous["file_id"] if previous else None
        try:
            new_file_id = _import(client, item, job)
        except ValueError:
            # Unsupported, too large, unreadable, or the same content as a file PEKA has (such as a
            # rename): keep what PEKA has and wait for the next edit.
            google_drive_repository.record_synced(drive_id, old_file_id, item["modifiedTime"])
            skipped += 1
            continue
        except (GoogleDriveRequestError, httpx.HTTPError):
            failed += 1  # not recorded, so the next run tries again
            continue
        if old_file_id:
            delete_file(old_file_id, job["user_id"], is_admin=True)
            updated += 1
        else:
            added += 1
        google_drive_repository.record_synced(drive_id, new_file_id, item["modifiedTime"])

    # Safe only because _list_tree raised on any listing error: a partial list would delete good files.
    for drive_id in known.keys() - current.keys():
        if known[drive_id]["file_id"]:
            delete_file(known[drive_id]["file_id"], job["user_id"], is_admin=True)
            removed += 1
        google_drive_repository.forget_synced(drive_id)

    result = f"{added} added, {updated} updated, {removed} removed"
    if skipped:
        result += f", {skipped} skipped (unsupported, too large, or duplicate)"
    if failed:
        result += f", {failed} failed to download and will retry"
    return result + "."


def _import(client: httpx.Client, item: dict, job: dict) -> UUID:
    """Store one listed Drive file and return its file ID. ValueError: PEKA cannot or need not store it."""
    mime_type = item["mimeType"]
    # Other native Google types (shortcuts, forms, drawings) have no content to download.
    native = mime_type.startswith("application/vnd.google-apps.")
    if mime_type not in EXPORTS and (native or Path(item["name"]).suffix.lower() not in FILE_CATEGORIES):
        raise ValueError(f"{item['name']} is not a supported file type")
    if int(item.get("size", 0)) > settings.max_upload_bytes:  # native Google files have no size
        raise FileTooLargeError(f"{item['name']} is too large")
    upload = _download(client, item["id"], item["name"], item["mimeType"])
    try:
        return store_files([upload], job["user_id"], [job["access_level"]])[0]["id"]
    finally:
        upload.file.close()
