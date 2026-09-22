from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4

import pymupdf

from app.auth import routes as auth_routes
from app.files import service


def test_files_require_login_and_support_upload_list_download(client, monkeypatch, tmp_path):
    assert client.get("/files").status_code == 401
    assert client.post("/files", files={"files": ("report.pdf", b"data", "application/pdf")}).status_code == 401

    account = {"id": uuid4(), "email": "user@example.com", "role": "staff",
               "token_version": 0, "is_active": True}
    token = auth_routes.create_access_token(str(account["id"]), account["role"], account["token_version"])
    headers = {"Authorization": f"Bearer {token}"}
    intruder = {"id": uuid4(), "email": "other@example.com", "role": "staff",
                "token_version": 0, "is_active": True}
    accounts = {account["id"]: account, intruder["id"]: intruder}
    records = []

    def create_many(files, author_id):
        created = [
            {"id": uuid4(), "path": path, "content_type": content_type, "sha256": sha256,
             "author_id": author_id, "access_level": access_level,
             "created_at": datetime.now(timezone.utc),
             "okf_status": "queued", "okf_attempts": 0, "okf_error": None}
            for path, content_type, sha256, access_level in files
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
    def retry_failed(file_id):
        record = next(record for record in records if record["id"] == file_id)
        if record["okf_status"] != "failed":
            return False
        record.update(okf_status="queued", okf_attempts=0, okf_error=None)
        return True

    monkeypatch.setattr(service.okf_jobs_repository, "retry_failed", retry_failed)

    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "Study material")
        pdf_data = pdf.tobytes()

    response = client.post(
        "/files",
        headers=headers,
        files=[
            ("files", ("report.pdf", pdf_data, "application/pdf")),
            ("files", ("notes.txt", b"notes", "text/plain")),
        ],
    )

    assert response.status_code == 201
    assert [item["path"] for item in response.json()] == ["pdf/report.pdf", "others/notes.txt"]
    assert response.json()[0]["sha256"] == hashlib.sha256(pdf_data).hexdigest()
    assert response.json()[1]["sha256"] == hashlib.sha256(b"notes").hexdigest()
    assert all(item["access_level"] == "general" for item in response.json())
    assert (tmp_path / "pdf" / "report.pdf").read_bytes() == pdf_data
    extracted_files = list((tmp_path / "extracted").glob("*.json"))
    assert len(extracted_files) == 2
    extractions = {
        record["source_filename"]: (path, record)
        for path in extracted_files
        for record in [json.loads(path.read_text(encoding="utf-8"))]
    }
    extracted_path, extraction = extractions["report.pdf"]
    assert extraction["source_path"] == str((tmp_path / "pdf" / "report.pdf").resolve())
    assert extraction["source_sha256"] == hashlib.sha256(pdf_data).hexdigest()
    assert extraction["sections"] == [{"page": 1, "text": "Study material"}]
    assert extractions["notes.txt"][1]["sections"] == [{"text": "notes"}]
    assert client.get("/files", headers=headers).json() == response.json()
    download = client.get(f"/files/{records[0]['id']}", headers=headers)
    assert download.status_code == 200
    assert download.content == pdf_data
    assert 'filename="report.pdf"' in download.headers["content-disposition"]

    intruder_token = auth_routes.create_access_token(
        str(intruder["id"]), intruder["role"], intruder["token_version"]
    )
    records[0].update(okf_status="failed", okf_attempts=3, okf_error="llama unavailable")
    retry = client.post(f"/files/{records[0]['id']}/retry-okf", headers=headers)
    assert retry.status_code == 200
    assert retry.json()["okf_status"] == "queued"
    assert retry.json()["okf_attempts"] == 0
    assert client.post(f"/files/{records[0]['id']}/retry-okf", headers=headers).status_code == 409
    assert client.delete(
        f"/files/{records[0]['id']}",
        headers={"Authorization": f"Bearer {intruder_token}"},
    ).status_code == 403
    assert client.delete(f"/files/{records[0]['id']}", headers=headers).status_code == 204
    assert not (tmp_path / "pdf" / "report.pdf").exists()
    assert not extracted_path.exists()


def test_access_level_patch_requires_admin(client, monkeypatch):
    file_id = uuid4()
    staff = {"id": uuid4(), "email": "staff@example.com", "role": "staff",
             "token_version": 0, "is_active": True}
    admin = {"id": uuid4(), "email": "admin@example.com", "role": "admin",
             "token_version": 0, "is_active": True}
    accounts = {staff["id"]: staff, admin["id"]: admin}

    def token_for(account):
        return {"Authorization": f"Bearer {auth_routes.create_access_token(str(account['id']), account['role'], account['token_version'])}"}

    record = {"id": file_id, "path": "pdf/report.pdf", "content_type": "application/pdf",
              "sha256": None, "author_id": staff["id"], "access_level": "general",
              "created_at": datetime.now(timezone.utc),
              "okf_status": "completed", "okf_attempts": 1, "okf_error": None}

    def update_access_level(target_id, level):
        if target_id != file_id:
            return False
        record.update(access_level=level)
        return True

    monkeypatch.setattr(auth_routes, "current_user", lambda user_id: accounts[user_id])
    monkeypatch.setattr(service.files_repository, "update_access_level", update_access_level)
    monkeypatch.setattr(
        service.files_repository,
        "find_by_id",
        lambda target_id: record if target_id == file_id else None,
    )

    assert client.patch(f"/files/{file_id}/access-level", headers=token_for(staff),
                        json={"access_level": "confidential"}).status_code == 403
    assert client.patch(f"/files/{file_id}/access-level", headers=token_for(staff),
                        json={"access_level": "secret"}).status_code == 422

    changed = client.patch(f"/files/{file_id}/access-level", headers=token_for(admin),
                           json={"access_level": "confidential"})
    assert changed.status_code == 200
    assert changed.json()["access_level"] == "confidential"
    assert record["access_level"] == "confidential"

    missing = uuid4()
    assert client.patch(f"/files/{missing}/access-level", headers=token_for(admin),
                        json={"access_level": "general"}).status_code == 404


def test_download_hides_confidential_files_from_staff(client, monkeypatch, tmp_path):
    staff = {"id": uuid4(), "email": "staff@example.com", "role": "staff",
             "token_version": 0, "is_active": True}
    admin = {"id": uuid4(), "email": "admin@example.com", "role": "admin",
             "token_version": 0, "is_active": True}
    file_id = uuid4()
    record = {
        "id": file_id,
        "path": "pdf/private.pdf",
        "content_type": "application/pdf",
        "access_level": "confidential",
    }
    path = tmp_path / record["path"]
    path.parent.mkdir()
    path.write_bytes(b"private")

    monkeypatch.setattr(
        auth_routes,
        "current_user",
        lambda user_id: staff if user_id == staff["id"] else admin,
    )
    monkeypatch.setattr(service.settings, "file_storage_dir", tmp_path)
    monkeypatch.setattr(
        service.files_repository,
        "find_by_id",
        lambda target_id: record if target_id == file_id else None,
    )

    def token_for(account):
        token = auth_routes.create_access_token(
            str(account["id"]), account["role"], account["token_version"]
        )
        return {"Authorization": f"Bearer {token}"}

    assert client.get(f"/files/{file_id}", headers=token_for(staff)).status_code == 404
    download = client.get(f"/files/{file_id}", headers=token_for(admin))
    assert download.status_code == 200
    assert download.content == b"private"


def test_upload_rejects_unsupported_files_without_saving(client, monkeypatch, tmp_path):
    account = {"id": uuid4(), "email": "user@example.com", "role": "staff",
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
    account = {"id": uuid4(), "email": "user@example.com", "role": "staff",
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


def test_upload_rejects_oversized_files_without_saving(client, monkeypatch, tmp_path):
    account = {"id": uuid4(), "email": "user@example.com", "role": "staff",
               "token_version": 0, "is_active": True}
    token = auth_routes.create_access_token(str(account["id"]), account["role"], account["token_version"])
    monkeypatch.setattr(auth_routes, "current_user", lambda user_id: account)
    monkeypatch.setattr(service.settings, "file_storage_dir", tmp_path)
    monkeypatch.setattr(service.settings, "max_upload_bytes", 4)

    response = client.post(
        "/files",
        headers={"Authorization": f"Bearer {token}"},
        files={"files": ("notes.txt", b"notes", "text/plain")},
    )

    assert response.status_code == 413
    assert not list(tmp_path.rglob("*.txt"))


def test_upload_accepts_per_file_access_levels_and_restricts_confidential_to_admin(
    client, monkeypatch, tmp_path
):
    admin = {"id": uuid4(), "email": "admin@example.com", "role": "admin",
             "token_version": 0, "is_active": True}
    staff = {"id": uuid4(), "email": "staff@example.com", "role": "staff",
             "token_version": 0, "is_active": True}
    accounts = {admin["id"]: admin, staff["id"]: staff}
    records = []

    def create_many(files, author_id):
        created = [
            {"id": uuid4(), "path": path, "content_type": content_type, "sha256": sha256,
             "author_id": author_id, "access_level": access_level,
             "created_at": datetime.now(timezone.utc),
             "okf_status": "queued", "okf_attempts": 0, "okf_error": None}
            for path, content_type, sha256, access_level in files
        ]
        records.extend(created)
        return created

    def token_for(account):
        token = auth_routes.create_access_token(str(account["id"]), account["role"], account["token_version"])
        return {"Authorization": f"Bearer {token}"}

    monkeypatch.setattr(auth_routes, "current_user", lambda user_id: accounts[user_id])
    monkeypatch.setattr(service.settings, "file_storage_dir", tmp_path)
    monkeypatch.setattr(service.files_repository, "create_many", create_many)
    monkeypatch.setattr(service.files_repository, "exists_by_sha256", lambda sha256: False)

    response = client.post(
        "/files",
        headers=token_for(admin),
        files=[
            ("files", ("private.txt", b"private", "text/plain")),
            ("files", ("public.txt", b"public", "text/plain")),
            ("access_levels", (None, "confidential")),
            ("access_levels", (None, "general")),
        ],
    )

    assert response.status_code == 201, response.text
    assert [item["access_level"] for item in response.json()] == ["confidential", "general"]

    unauthorized = client.post(
        "/files",
        headers=token_for(staff),
        files=[
            ("files", ("staff-private.txt", b"private", "text/plain")),
            ("access_levels", (None, "confidential")),
        ],
    )
    assert unauthorized.status_code == 403
