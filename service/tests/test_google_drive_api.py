from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.auth import routes as auth_routes
from app.files.service import DuplicateFileError
from app.google_drive import service

REAL_CLIENT = httpx.Client


def login(monkeypatch, role="staff"):
    account = {"id": uuid4(), "email": "user@example.com", "role": role,
               "token_version": 0, "is_active": True}
    monkeypatch.setattr(auth_routes, "current_user", lambda user_id: account)
    token = auth_routes.create_access_token(str(account["id"]), role, 0)
    return account, {"Authorization": f"Bearer {token}"}


def configure(monkeypatch):
    monkeypatch.setattr(service.settings, "google_client_id", "client-id")
    monkeypatch.setattr(service.settings, "google_client_secret", SecretStr("client-secret"))
    monkeypatch.setattr(service.settings, "google_api_key", "api-key")
    monkeypatch.setattr(service.settings, "google_app_id", "123")
    tokens = {}
    monkeypatch.setattr(service.google_drive_repository, "save_refresh_token", tokens.__setitem__)
    monkeypatch.setattr(service.google_drive_repository, "find_refresh_token", tokens.get)
    monkeypatch.setattr(service.google_drive_repository, "delete", lambda user_id: tokens.pop(user_id, None))
    return tokens


def fake_token_endpoint(monkeypatch, response):
    calls = []

    def post(url, data, timeout):
        calls.append(data)
        return httpx.Response(response[0], json=response[1])

    monkeypatch.setattr(service.httpx, "post", post)
    return calls


def test_connect_requires_login_and_configuration(client, monkeypatch):
    assert client.get("/integrations/google/connect").status_code == 401
    _, headers = login(monkeypatch)
    monkeypatch.setattr(service.settings, "google_client_id", None)
    assert client.get("/integrations/google/connect", headers=headers).status_code == 503


def test_connect_callback_stores_refresh_token_for_state_user(client, monkeypatch):
    account, headers = login(monkeypatch)
    tokens = configure(monkeypatch)
    calls = fake_token_endpoint(monkeypatch, (200, {"access_token": "a", "refresh_token": "r"}))

    url = client.get("/integrations/google/connect", headers=headers).json()["url"]
    query = parse_qs(urlparse(url).query)
    assert query["scope"] == [service.SCOPE]
    assert query["access_type"] == ["offline"]

    response = client.get("/integrations/google/callback",
                          params={"code": "code-1", "state": query["state"][0]}, follow_redirects=False)
    assert response.headers["location"].endswith("/workspace/knowledge?google_drive=connected")
    assert tokens == {account["id"]: "r"}
    assert calls[0]["code"] == "code-1"


def test_callback_rejects_forged_state(client, monkeypatch):
    tokens = configure(monkeypatch)
    calls = fake_token_endpoint(monkeypatch, (200, {"access_token": "a", "refresh_token": "r"}))

    response = client.get("/integrations/google/callback",
                          params={"code": "code-1", "state": "forged"}, follow_redirects=False)
    assert response.headers["location"].endswith("google_drive=error")
    assert tokens == {} and calls == []


def test_picker_needs_connection_and_forgets_revoked_grant(client, monkeypatch):
    account, headers = login(monkeypatch)
    tokens = configure(monkeypatch)
    assert client.get("/integrations/google/picker", headers=headers).status_code == 409

    tokens[account["id"]] = "r"
    fake_token_endpoint(monkeypatch, (200, {"access_token": "fresh"}))
    assert client.get("/integrations/google/picker", headers=headers).json() == {
        "access_token": "fresh", "api_key": "api-key", "app_id": "123"}

    fake_token_endpoint(monkeypatch, (400, {"error": "invalid_grant"}))
    assert client.get("/integrations/google/picker", headers=headers).status_code == 409
    assert tokens == {}


def test_import_exports_google_docs_and_stores_files(client, monkeypatch):
    account, headers = login(monkeypatch, role="admin")
    tokens = configure(monkeypatch)
    tokens[account["id"]] = "r"
    fake_token_endpoint(monkeypatch, (200, {"access_token": "fresh"}))

    def drive(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer fresh"
        if request.url.path.endswith("/doc-1"):
            return httpx.Response(200, json={"name": "Plan", "mimeType": "application/vnd.google-apps.document"})
        if request.url.path.endswith("/doc-1/export"):
            return httpx.Response(200, content=b"docx-bytes")
        if request.url.params.get("alt") == "media":
            return httpx.Response(200, content=b"pdf-bytes")
        return httpx.Response(200, json={"name": "report.pdf", "mimeType": "application/pdf"})

    monkeypatch.setattr(service.httpx, "Client",
                        lambda **kwargs: REAL_CLIENT(transport=httpx.MockTransport(drive), **kwargs))
    stored = []

    def store_files(uploads, author_id, levels):
        stored.extend((upload.filename, upload.content_type, upload.file.read(), level)
                      for upload, level in zip(uploads, levels))
        return []

    monkeypatch.setattr(service, "store_files", store_files)

    response = client.post("/integrations/google/files", headers=headers, json={"files": [
        {"id": "doc-1"}, {"id": "pdf-1", "access_level": "confidential"}]})
    assert response.status_code == 201
    assert stored == [
        ("Plan.docx", service.EXPORTS["application/vnd.google-apps.document"][0], b"docx-bytes", "general"),
        ("report.pdf", "application/pdf", b"pdf-bytes", "confidential"),
    ]


def test_staff_cannot_import_confidential(client, monkeypatch):
    _, headers = login(monkeypatch)
    response = client.post("/integrations/google/files", headers=headers,
                           json={"files": [{"id": "x", "access_level": "confidential"}]})
    assert response.status_code == 403


DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def fake_drive(monkeypatch, tree, fail_folder=None):
    """`tree` maps a folder ID to its children: (id, name, mimeType, modifiedTime)."""
    items = {child[0]: child for children in tree.values() for child in children}

    def as_json(child):
        return dict(zip(("id", "name", "mimeType", "modifiedTime"), child))

    def drive(request: httpx.Request) -> httpx.Response:
        path, params = request.url.path, request.url.params
        if path == "/drive/v3/files":
            folder = params["q"].split("'")[1]
            if folder == fail_folder:
                return httpx.Response(500)
            children = tree[folder]
            if "pageToken" not in params and len(children) > 1:  # two pages, to cover paging
                return httpx.Response(200, json={"files": [as_json(children[0])], "nextPageToken": "next"})
            rest = children[1:] if "pageToken" in params else children
            return httpx.Response(200, json={"files": [as_json(child) for child in rest]})
        file_id = path.rsplit("/", 1)[1]
        if params.get("fields") == "trashed":
            return httpx.Response(200, json={"trashed": False})
        if params.get("alt") == "media":
            return httpx.Response(200, content=file_id.encode())
        return httpx.Response(200, json={"name": items[file_id][1], "mimeType": items[file_id][2]})

    monkeypatch.setattr(service.httpx, "Client",
                        lambda **kwargs: REAL_CLIENT(transport=httpx.MockTransport(drive), **kwargs))


def fake_sync(monkeypatch, job, known):
    """In-memory sync tables; `known` is the synced-files table and changes in place."""
    runs, events, stored, deleted = [], [], [], []
    repository = service.google_drive_repository
    monkeypatch.setattr(repository, "is_due", lambda: True)
    monkeypatch.setattr(repository, "claim_due", lambda: job)
    monkeypatch.setattr(repository, "synced_files", lambda: {key: dict(value) for key, value in known.items()})
    monkeypatch.setattr(repository, "record_synced", lambda drive_id, file_id, modified: known.__setitem__(
        drive_id, {"file_id": file_id, "modified_time": modified}))
    monkeypatch.setattr(repository, "forget_synced", known.pop)
    monkeypatch.setattr(repository, "finish_run", lambda folder_id, result: runs.append(result))
    monkeypatch.setattr(service, "access_token", lambda user_id, scope=None: "fresh")
    monkeypatch.setattr(service, "record_audit_event", lambda event, **kwargs: events.append(event))

    def store_files(uploads, author_id, levels):
        name = uploads[0].filename
        if name == "dup.pdf":
            raise DuplicateFileError("A file with identical content already exists")
        stored.append((name, uploads[0].file.read(), levels[0]))
        return [{"id": f"file-{name}"}]

    monkeypatch.setattr(service, "store_files", store_files)
    monkeypatch.setattr(service, "delete_file", lambda file_id, user_id, is_admin: deleted.append(file_id))
    return runs, events, stored, deleted


SYNC_TREE = {
    "root": [
        ("same", "same.pdf", "application/pdf", "1"),
        ("unimported", "unimported.pdf", "application/pdf", "1"),
        ("edited", "edited.pdf", "application/pdf", "2"),
        ("sub", "Sub", service.FOLDER_MIME_TYPE, "1"),
    ],
    "sub": [
        ("unimported-then-edited", "old.docx", DOCX, "2"),
        ("new", "new.pdf", "application/pdf", "1"),
        ("video", "clip.mp4", "video/mp4", "1"),
        ("shortcut", "report.pdf", "application/vnd.google-apps.shortcut", "1"),
        ("dup", "dup.pdf", "application/pdf", "1"),
    ],
}


def test_sync_imports_new_and_edited_files_and_removes_deleted_ones(monkeypatch):
    configure(monkeypatch)
    fake_drive(monkeypatch, SYNC_TREE)
    known = {
        "same": {"file_id": "f-same", "modified_time": "1"},
        "unimported": {"file_id": None, "modified_time": "1"},
        "edited": {"file_id": "f-edited", "modified_time": "1"},
        "unimported-then-edited": {"file_id": None, "modified_time": "1"},
        "gone": {"file_id": "f-gone", "modified_time": "1"},
        "gone-unimported": {"file_id": None, "modified_time": "1"},
    }
    job = {"user_id": uuid4(), "folder_id": "root", "access_level": "confidential",
           "owner_is_admin": True}
    runs, events, stored, deleted = fake_sync(monkeypatch, job, known)

    service.sync_folder()

    assert sorted(stored) == [("edited.pdf", b"edited", "confidential"), ("new.pdf", b"new", "confidential"),
                              ("old.docx", b"unimported-then-edited", "confidential")]
    assert sorted(deleted) == ["f-edited", "f-gone"]
    assert known == {
        "same": {"file_id": "f-same", "modified_time": "1"},
        "unimported": {"file_id": None, "modified_time": "1"},  # skipped before and unchanged since
        "edited": {"file_id": "file-edited.pdf", "modified_time": "2"},
        "unimported-then-edited": {"file_id": "file-old.docx", "modified_time": "2"},
        "new": {"file_id": "file-new.pdf", "modified_time": "1"},
        "video": {"file_id": None, "modified_time": "1"},
        "shortcut": {"file_id": None, "modified_time": "1"},
        "dup": {"file_id": None, "modified_time": "1"},
    }
    assert runs == ["2 added, 1 updated, 1 removed, 3 skipped (unsupported, too large, or duplicate)."]
    assert events == ["drive_sync_completed"]


def test_sync_deletes_nothing_when_any_folder_fails_to_list(monkeypatch):
    configure(monkeypatch)
    fake_drive(monkeypatch, SYNC_TREE, fail_folder="sub")
    known = {"gone": {"file_id": "f-gone", "modified_time": "1"}}
    job = {"user_id": uuid4(), "folder_id": "root", "access_level": "general",
           "owner_is_admin": True}
    runs, events, stored, deleted = fake_sync(monkeypatch, job, known)

    service.sync_folder()

    assert stored == [] and deleted == []
    assert known == {"gone": {"file_id": "f-gone", "modified_time": "1"}}
    assert runs == ["Sync failed: Unable to list the synced Google Drive folder"]
    assert events == ["drive_sync_failed"]


def test_first_sync_imports_files_already_in_the_folder(monkeypatch):
    configure(monkeypatch)
    fake_drive(monkeypatch, SYNC_TREE)
    job = {"user_id": uuid4(), "folder_id": "root", "access_level": "general", "owner_is_admin": True}
    runs, _, stored, deleted = fake_sync(monkeypatch, job, {})

    service.sync_folder()

    assert sorted(name for name, _, _ in stored) == ["edited.pdf", "new.pdf", "old.docx", "same.pdf", "unimported.pdf"]
    assert deleted == []
    assert runs == ["5 added, 0 updated, 0 removed, 3 skipped (unsupported, too large, or duplicate)."]


def test_sync_stops_when_the_owner_is_no_longer_an_admin(monkeypatch):
    configure(monkeypatch)
    fake_drive(monkeypatch, SYNC_TREE)
    job = {"user_id": uuid4(), "folder_id": "root", "access_level": "general",
           "owner_is_admin": False}
    runs, events, stored, deleted = fake_sync(monkeypatch, job, {"gone": {"file_id": "f-gone", "modified_time": "1"}})

    service.sync_folder()

    assert stored == [] and deleted == []
    assert runs[0].startswith("Sync failed: the admin who set it up is no longer an active admin")
    assert events == ["drive_sync_failed"]


def test_sync_scope_is_required_for_folder_sync(monkeypatch):
    account, _ = login(monkeypatch, role="admin")
    tokens = configure(monkeypatch)
    tokens[account["id"]] = "r"
    fake_token_endpoint(monkeypatch, (200, {"access_token": "fresh", "scope": service.SCOPE}))
    with pytest.raises(service.GoogleDriveNotConnectedError):
        service.access_token(account["id"], service.SYNC_SCOPE)
    fake_token_endpoint(monkeypatch, (200, {"access_token": "fresh", "scope": f"{service.SCOPE} {service.SYNC_SCOPE}"}))
    assert service.access_token(account["id"], service.SYNC_SCOPE) == "fresh"


def test_folder_sync_is_admin_only(client, monkeypatch):
    configure(monkeypatch)
    _, headers = login(monkeypatch)
    assert client.get("/integrations/google/sync", headers=headers).status_code == 403
    assert client.post("/integrations/google/sync/run", headers=headers).status_code == 403
    assert client.get("/integrations/google/sync/connect", headers=headers).status_code == 403
    assert client.get("/integrations/google/sync/picker", headers=headers).status_code == 403


def test_sync_settings_reject_bad_timezone_and_folder_id(client, monkeypatch):
    _, headers = login(monkeypatch, role="admin")
    body = {"folder_id": "abc_123-X", "folder_name": "Policies", "timezone": "Asia/Phnom_Penh", "sync_time": "22:30"}
    assert client.put("/integrations/google/sync", headers=headers,
                      json={**body, "timezone": "Mars/Base"}).status_code == 422
    assert client.put("/integrations/google/sync", headers=headers,
                      json={**body, "folder_id": "x' or name contains '"}).status_code == 422


def test_sync_connect_returns_to_admin_settings(client, monkeypatch):
    account, headers = login(monkeypatch, role="admin")
    tokens = configure(monkeypatch)
    fake_token_endpoint(monkeypatch, (200, {"access_token": "a", "refresh_token": "r"}))

    url = client.get("/integrations/google/sync/connect", headers=headers).json()["url"]
    query = parse_qs(urlparse(url).query)
    assert query["scope"] == [service.SYNC_SCOPE]

    response = client.get("/integrations/google/callback",
                          params={"code": "c", "state": query["state"][0]}, follow_redirects=False)
    assert response.headers["location"].endswith("/workspace/admin/settings?google_drive=connected")
    assert tokens == {account["id"]: "r"}

    refused = client.get("/integrations/google/callback",
                         params={"error": "access_denied", "state": query["state"][0]}, follow_redirects=False)
    assert refused.headers["location"].endswith("/workspace/admin/settings?google_drive=error")
