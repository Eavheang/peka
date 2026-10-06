from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
from pydantic import SecretStr

from app.auth import routes as auth_routes
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
