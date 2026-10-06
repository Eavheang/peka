from datetime import datetime, timedelta, timezone
from tempfile import SpooledTemporaryFile
from urllib.parse import urlencode
from uuid import UUID

import httpx
import jwt
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.config import settings
from app.files.service import FileTooLargeError, store_files
from app.google_drive.repository import google_drive_repository

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
FILES_URL = "https://www.googleapis.com/drive/v3/files"
SCOPE = "https://www.googleapis.com/auth/drive.file"

# Native Google files have no binary content; export them to the matching Office format.
EXPORTS = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"),
}


class GoogleDriveNotConfiguredError(RuntimeError):
    pass


class GoogleDriveNotConnectedError(RuntimeError):
    pass


class GoogleDriveRequestError(RuntimeError):
    pass


def _client_credentials() -> tuple[str, str]:
    client_id, client_secret = settings.google_client_id, settings.google_client_secret
    if not (client_id and client_secret and settings.google_api_key and settings.google_app_id):
        raise GoogleDriveNotConfiguredError("Google Drive is not configured")
    return client_id, client_secret.get_secret_value()


def authorization_url(user_id: UUID) -> str:
    client_id, _ = _client_credentials()
    now = datetime.now(timezone.utc)
    # Signed state ties the callback to the user who started it, without a server-side session.
    state = jwt.encode(
        {"sub": str(user_id), "typ": "google_drive_state", "iss": settings.jwt_issuer,
         "aud": settings.jwt_audience, "iat": now, "exp": now + timedelta(minutes=10)},
        settings.jwt_secret_key.get_secret_value(), algorithm="HS256",
    )
    return f"{AUTH_URL}?" + urlencode({
        "client_id": client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",  # always return a refresh token, even on reconnect
        "include_granted_scopes": "true",
        "state": state,
    })


def complete_connection(code: str, state: str) -> None:
    client_id, client_secret = _client_credentials()
    claims = jwt.decode(
        state, settings.jwt_secret_key.get_secret_value(), algorithms=["HS256"],
        issuer=settings.jwt_issuer, audience=settings.jwt_audience,
        options={"require": ["sub", "typ", "exp"]},
    )
    if claims["typ"] != "google_drive_state":
        raise jwt.InvalidTokenError("invalid state")
    response = httpx.post(TOKEN_URL, data={
        "code": code, "client_id": client_id, "client_secret": client_secret,
        "redirect_uri": settings.google_redirect_uri, "grant_type": "authorization_code",
    }, timeout=30)
    if response.status_code != 200 or "refresh_token" not in response.json():
        raise GoogleDriveRequestError("Google did not return a refresh token")
    google_drive_repository.save_refresh_token(UUID(claims["sub"]), response.json()["refresh_token"])


def access_token(user_id: UUID) -> str:
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
    return response.json()["access_token"]


def picker_config(user_id: UUID) -> dict:
    return {"access_token": access_token(user_id), "api_key": settings.google_api_key,
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


def _download(client: httpx.Client, file_id: str) -> UploadFile:
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
