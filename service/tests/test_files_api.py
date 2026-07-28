from datetime import datetime, timezone
import hashlib
from uuid import uuid4

from app.auth import routes as auth_routes
from app.files import service


def test_files_require_login_and_support_upload_list_download(client, monkeypatch, tmp_path):
    assert client.get("/files").status_code == 401
    assert client.post("/files", files={"files": ("report.pdf", b"data", "application/pdf")}).status_code == 401

    account = {"id": uuid4(), "email": "user@example.com", "role": "member",
               "token_version": 0, "is_active": True}
    token = auth_routes.create_access_token(str(account["id"]), account["role"], account["token_version"])
    headers = {"Authorization": f"Bearer {token}"}
    intruder = {"id": uuid4(), "email": "other@example.com", "role": "member",
                "token_version": 0, "is_active": True}
    accounts = {account["id"]: account, intruder["id"]: intruder}
    records = []

    def create_many(files, author_id):
        created = [
            {"id": uuid4(), "path": path, "content_type": content_type, "sha256": sha256,
             "author_id": author_id, "created_at": datetime.now(timezone.utc)}
            for path, content_type, sha256 in files
        ]
        records.extend(created)
        return created

    monkeypatch.setattr(auth_routes, "current_user", lambda user_id: accounts[user_id])
    monkeypatch.setattr(service.settings, "file_storage_dir", tmp_path)
    monkeypatch.setattr(service.files_repository, "create_many", create_many)
    monkeypatch.setattr(service.files_repository, "exists_by_sha256", lambda sha256: False)
    monkeypatch.setattr(service.files_repository, "list_all", lambda: records)
    monkeypatch.setattr(
        service.files_repository,
        "find_by_id",
        lambda file_id: next((record for record in records if record["id"] == file_id), None),
    )
    monkeypatch.setattr(
        service.files_repository,
        "delete",
        lambda file_id: records.__setitem__(slice(None), [record for record in records if record["id"] != file_id]),
    )

    response = client.post(
        "/files",
        headers=headers,
        files=[
            ("files", ("report.pdf", b"pdf-data", "application/pdf")),
            ("files", ("notes.txt", b"notes", "text/plain")),
        ],
    )

    assert response.status_code == 201
    assert [item["path"] for item in response.json()] == ["pdf/report.pdf", "others/notes.txt"]
    assert response.json()[0]["sha256"] == hashlib.sha256(b"pdf-data").hexdigest()
    assert response.json()[1]["sha256"] == hashlib.sha256(b"notes").hexdigest()
    assert (tmp_path / "pdf" / "report.pdf").read_bytes() == b"pdf-data"
    assert client.get("/files", headers=headers).json() == response.json()
    download = client.get(f"/files/{records[0]['id']}", headers=headers)
    assert download.status_code == 200
    assert download.content == b"pdf-data"
    assert 'filename="report.pdf"' in download.headers["content-disposition"]

    intruder_token = auth_routes.create_access_token(
        str(intruder["id"]), intruder["role"], intruder["token_version"]
    )
    assert client.delete(
        f"/files/{records[0]['id']}",
        headers={"Authorization": f"Bearer {intruder_token}"},
    ).status_code == 403
    assert client.delete(f"/files/{records[0]['id']}", headers=headers).status_code == 204
    assert not (tmp_path / "pdf" / "report.pdf").exists()


def test_upload_rejects_unsupported_files_without_saving(client, monkeypatch, tmp_path):
    account = {"id": uuid4(), "email": "user@example.com", "role": "member",
               "token_version": 0, "is_active": True}
    token = auth_routes.create_access_token(str(account["id"]), account["role"], account["token_version"])
    monkeypatch.setattr(auth_routes, "current_user", lambda user_id: account)
    monkeypatch.setattr(service.settings, "file_storage_dir", tmp_path)

    response = client.post(
        "/files",
        headers={"Authorization": f"Bearer {token}"},
        files={"files": ("image.png", b"image", "image/png")},
    )

    assert response.status_code == 415
    assert not list(tmp_path.rglob("*"))


def test_upload_rejects_duplicate_content(client, monkeypatch, tmp_path):
    account = {"id": uuid4(), "email": "user@example.com", "role": "member",
               "token_version": 0, "is_active": True}
    token = auth_routes.create_access_token(str(account["id"]), account["role"], account["token_version"])
    monkeypatch.setattr(auth_routes, "current_user", lambda user_id: account)
    monkeypatch.setattr(service.settings, "file_storage_dir", tmp_path)
    monkeypatch.setattr(service.files_repository, "exists_by_sha256", lambda sha256: sha256 == hashlib.sha256(b"same").hexdigest())

    response = client.post(
        "/files",
        headers={"Authorization": f"Bearer {token}"},
        files={"files": ("copy.pdf", b"same", "application/pdf")},
    )

    assert response.status_code == 409
    assert not list(tmp_path.rglob("*.pdf"))
