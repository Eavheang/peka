"""Audit writers against a real Postgres, not a mocked repository.

Skipped unless TEST_DATABASE_URL points at a database whose name contains "test".
CI sets that variable. Locally:

    TEST_DATABASE_URL=postgresql://peka:peka_dev_password@localhost:5432/peka_test python -m pytest tests/test_audit_writers_database.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from app.auth.security import create_access_token, hash_password
from app.chat.schemas import ChatResponse
from app.chat.service import persist_response
from app.config import settings
from app.engine import source_extractor as extractor
from app.engine.okf import worker

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="needs PostgreSQL: set TEST_DATABASE_URL"
)
SERVICE_DIR = Path(__file__).resolve().parents[1]


def execute(sql: str, params=()):
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True, row_factory=dict_row) as connection:
        cursor = connection.execute(sql, params)
        if cursor.description is None:
            return []
        return cursor.fetchall()


@pytest.fixture(scope="module")
def database():
    name = urlparse(TEST_DATABASE_URL).path.lstrip("/")
    assert "test" in name, "TEST_DATABASE_URL must point at a dedicated test database"
    original = settings.database_url
    settings.database_url = TEST_DATABASE_URL
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=SERVICE_DIR, env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
        check=True, capture_output=True,
    )
    yield
    settings.database_url = original


def _insert_user(role: str, password: str | None = None) -> dict:
    email = f"audit-{uuid4().hex}@example.test"
    password_hash = hash_password(password or "correct password long")
    return execute(
        "INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s) "
        "RETURNING id, email, role, token_version, is_active",
        (email, password_hash, role),
    )[0]


def _events_for_actor(actor_id, summary: str) -> list[dict]:
    return execute(
        "SELECT type, summary, metadata, actor_id FROM audit_events "
        "WHERE actor_id = %s AND summary = %s",
        (actor_id, summary),
    )


def test_sync_complete_and_terminal_fail_write_rows(database, monkeypatch, tmp_path):
    author = _insert_user("admin")
    run = uuid4().hex
    relative = f"pdf/audit-{run}.pdf"
    source = tmp_path / relative
    source.parent.mkdir(parents=True)
    source.write_text("source", encoding="utf-8")
    extraction = tmp_path / "extracted" / f"{extractor.source_id_for(source)}.json"
    extraction.parent.mkdir()
    extraction.write_text(json.dumps({"source_id": "source-1", "sections": []}), encoding="utf-8")
    file_id = execute(
        "INSERT INTO files (path, content_type, sha256, author_id) "
        "VALUES (%s, 'text/plain', %s, %s) RETURNING id",
        (relative, f"sha-{run}", author["id"]),
    )[0]["id"]
    execute(
        "INSERT INTO okf_jobs (file_id, status, attempts) VALUES (%s, 'queued', 0)",
        (file_id,),
    )
    monkeypatch.setattr(worker.settings, "file_storage_dir", tmp_path)
    monkeypatch.setattr(worker, "convert_to_okf", lambda extraction, storage: {"files": []})
    monkeypatch.setattr(worker, "parse_okf_chunks", lambda result: [])
    monkeypatch.setattr(worker, "embed_chunks", lambda chunks: [])
    monkeypatch.setattr(
        worker, "knowledge_chunks_repository",
        type("Chunks", (), {"swap_active_set": lambda *args: None})(),
    )

    assert worker.process_next_job()
    completed = execute(
        "SELECT summary, metadata FROM audit_events "
        "WHERE type = 'sync' AND metadata->>'file_id' = %s AND metadata->>'status' = 'completed'",
        (str(file_id),),
    )
    assert len(completed) == 1
    assert completed[0]["summary"] == "Sync completed"
    assert completed[0]["metadata"] == {"event": "sync_completed", "file_id": str(file_id), "status": "completed"}

    execute(
        "UPDATE okf_jobs SET status = 'queued', attempts = 2, last_error = NULL WHERE file_id = %s",
        (file_id,),
    )
    monkeypatch.setattr(
        worker, "convert_to_okf",
        lambda extraction, storage: (_ for _ in ()).throw(RuntimeError("terminal")),
    )
    assert worker.process_next_job()
    failed = execute(
        "SELECT summary, metadata FROM audit_events "
        "WHERE type = 'sync' AND metadata->>'file_id' = %s AND metadata->>'status' = 'failed'",
        (str(file_id),),
    )
    assert len(failed) == 1
    assert failed[0]["summary"] == "Sync failed"


def test_chat_turn_writes_the_created_conversation_id(database):
    owner = _insert_user("staff")
    prompt = f"do-not-store-{uuid4().hex}"
    saved = persist_response(prompt, owner["id"], ChatResponse(answer="ok", refused=False, citations=[]))
    rows = execute(
        "SELECT summary, metadata, actor_id FROM audit_events "
        "WHERE type = 'query' AND metadata->>'conversation_id' = %s",
        (str(saved.conversation_id),),
    )
    assert len(rows) == 1
    assert rows[0]["summary"] == "Chat turn"
    assert rows[0]["actor_id"] == owner["id"]
    assert rows[0]["metadata"] == {"event": "chat_turn", "conversation_id": str(saved.conversation_id)}
    assert prompt not in json.dumps(rows[0]["metadata"])
    stored = execute("SELECT id FROM conversations WHERE id = %s", (saved.conversation_id,))
    assert stored[0]["id"] == saved.conversation_id


def test_login_writes_login_success(database, client):
    password = "correct password long"
    user = _insert_user("admin", password)
    response = client.post("/auth/login", json={"email": user["email"], "password": password})
    assert response.status_code == 200
    rows = _events_for_actor(user["id"], "Login success")
    assert len(rows) == 1
    assert rows[0]["type"] == "system"
    assert rows[0]["metadata"] == {"event": "login_success"}


def test_admin_gate_deny_writes_system_event(database, client):
    staff = _insert_user("staff")
    token = create_access_token(str(staff["id"]), staff["role"], staff["token_version"])
    response = client.patch(
        f"/files/{uuid4()}/access-level",
        headers={"Authorization": f"Bearer {token}"},
        json={"access_level": "confidential"},
    )
    assert response.status_code == 403
    rows = _events_for_actor(staff["id"], "Admin gate deny")
    assert len(rows) == 1
    assert rows[0]["type"] == "system"
    assert rows[0]["metadata"]["event"] == "admin_gate_deny"
    assert rows[0]["metadata"]["path"].endswith("/access-level")
