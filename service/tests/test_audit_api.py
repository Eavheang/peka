import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.audit.repository import audit_repository
from app.audit.service import _encode_cursor, list_events
from app.audit.service import record_audit_event
from app.auth import routes as auth_routes
from app.auth.security import create_access_token
from app.chat import service as chat_service
from app.chat.schemas import ChatResponse
from app.engine import source_extractor as extractor
from app.engine.okf import worker


def account(role="staff"):
    return {
        "id": uuid4(),
        "email": f"{role}@example.com",
        "role": role,
        "token_version": 0,
        "is_active": True,
        "display_name": "",
    }


def bearer(user):
    token = create_access_token(str(user["id"]), user["role"], user["token_version"])
    return {"Authorization": f"Bearer {token}"}


def use_accounts(monkeypatch, *users):
    by_id = {user["id"]: user for user in users}
    monkeypatch.setattr(auth_routes, "current_user", lambda user_id: by_id.get(user_id))


class MemoryAuditStore:
    def __init__(self):
        self.rows = []

    def insert(self, event_type, summary, actor_id=None, metadata=None):
        created_at = datetime.now(timezone.utc)
        if self.rows and self.rows[-1]["created_at"] >= created_at:
            created_at = self.rows[-1]["created_at"] + timedelta(microseconds=1)
        self.rows.append({
            "id": uuid4(),
            "type": event_type,
            "actor_id": actor_id,
            "summary": summary,
            "metadata": metadata or {},
            "created_at": created_at,
        })

    def fetch(self, event_type, limit, cursor):
        rows = self.rows
        if event_type is not None:
            rows = [row for row in rows if row["type"] == event_type]
        rows = sorted(rows, key=lambda row: (row["created_at"], row["id"]), reverse=True)
        if cursor is not None:
            rows = [row for row in rows if (row["created_at"], row["id"]) < cursor]
        return rows[:limit]


class ScriptedJobs:
    def __init__(self, file_id, path):
        self.file_id = file_id
        self.path = path
        self.attempts = 0
        self.should_fail = False

    def claim_next(self):
        self.attempts += 1
        return {"file_id": self.file_id, "path": self.path}

    def complete(self, file_id):
        return None

    def fail(self, file_id, error):
        return "failed" if self.attempts >= 3 else "queued"


def install_store(monkeypatch):
    store = MemoryAuditStore()
    monkeypatch.setattr(audit_repository, "insert", store.insert)
    monkeypatch.setattr(audit_repository, "fetch", store.fetch)
    return store


def _write_extraction(storage, relative_source):
    source = storage / relative_source
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("source", encoding="utf-8")
    extraction_path = storage / "extracted" / f"{extractor.source_id_for(source)}.json"
    extraction_path.parent.mkdir(exist_ok=True)
    extraction_path.write_text(json.dumps({"source_id": "source-1", "sections": []}), encoding="utf-8")


def _prepare_worker(monkeypatch, tmp_path, jobs, convert):
    _write_extraction(tmp_path, jobs.path)
    monkeypatch.setattr(worker, "okf_jobs_repository", jobs)
    monkeypatch.setattr(worker.settings, "file_storage_dir", tmp_path)
    monkeypatch.setattr(worker, "convert_to_okf", convert)
    monkeypatch.setattr(worker, "parse_okf_chunks", lambda result: [])
    monkeypatch.setattr(worker, "embed_chunks", lambda chunks: [])
    monkeypatch.setattr(
        worker,
        "knowledge_chunks_repository",
        type("Chunks", (), {"swap_active_set": lambda *args: None})(),
    )


def _persist_new_chat(monkeypatch, owner_id, prompt):
    conversation_id = uuid4()
    created_at = datetime.now(timezone.utc)

    def create_exchange(owner_id, title, query, response, conversation_id=None, status="completed", new_conversation_id=None, replace_ids=None):
        assert conversation_id is None
        return {
            "conversation": {
                "id": saved_id,
                "owner_id": owner_id,
                "title": title,
                "created_at": created_at,
                "updated_at": created_at,
            },
            "messages": [
                {
                    "id": uuid4(), "role": "user", "content": query, "refused": False,
                    "citations": [], "status": "completed", "created_at": created_at,
                },
                {
                    "id": uuid4(), "role": "assistant", "content": response.answer, "refused": False,
                    "citations": [], "status": "completed", "created_at": created_at,
                },
            ],
        }

    saved_id = conversation_id
    monkeypatch.setattr(chat_service.chat_repository, "create_exchange", create_exchange)
    saved = chat_service.persist_response(
        prompt, owner_id, ChatResponse(answer="ok", refused=False, citations=[]),
    )
    assert saved.conversation_id == conversation_id
    return conversation_id


def test_staff_cannot_list_audit_events(client, monkeypatch):
    install_store(monkeypatch)
    staff = account("staff")
    use_accounts(monkeypatch, staff)

    response = client.get("/admin/audit-events", headers=bearer(staff))

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin role required"


def test_admin_list_includes_sync_query_login_and_admin_deny(client, monkeypatch, tmp_path):
    install_store(monkeypatch)
    admin = account("admin")
    staff = account("staff")
    use_accounts(monkeypatch, admin, staff)
    prompt = "super-secret-prompt-body-should-not-be-stored"
    file_id = uuid4()
    jobs = ScriptedJobs(file_id, "pdf/policy.pdf")
    conversions = {"n": 0}

    def convert(extraction, storage):
        conversions["n"] += 1
        if jobs.should_fail:
            raise RuntimeError("terminal")
        return {"files": []}

    _prepare_worker(monkeypatch, tmp_path, jobs, convert)
    assert worker.process_next_job()
    jobs.should_fail = True
    jobs.attempts = 0
    assert worker.process_next_job()
    jobs.attempts = 2
    assert worker.process_next_job()

    conversation_id = _persist_new_chat(monkeypatch, staff["id"], prompt)

    def stop_model(*args, **kwargs):
        raise RuntimeError("model")

    monkeypatch.setattr(chat_service, "_search_plan", stop_model)
    try:
        chat_service.answer_from_knowledge(prompt, "staff")
    except RuntimeError:
        pass

    monkeypatch.setattr(auth_routes, "authenticate", lambda email, password: admin)
    login = client.post("/auth/login", json={"email": admin["email"], "password": "x"})
    assert login.status_code == 200
    denied = client.patch(
        f"/files/{uuid4()}/access-level",
        headers=bearer(staff),
        json={"access_level": "confidential"},
    )
    assert denied.status_code == 403

    response = client.get("/admin/audit-events", headers=bearer(admin))
    assert response.status_code == 200
    body = response.json()
    assert "next_cursor" in body
    assert "nextCursor" not in body
    types = {item["type"] for item in body["items"]}
    summaries = {item["summary"] for item in body["items"]}
    assert {"sync", "query", "system"} <= types
    assert {"Sync completed", "Sync failed", "Chat turn", "Login success", "Admin gate deny"} <= summaries
    sync_events = [item for item in body["items"] if item["type"] == "sync"]
    assert [item["summary"] for item in sync_events].count("Sync failed") == 1
    assert all(set(item["metadata"]) == {"event", "file_id", "status"} for item in sync_events)
    assert {item["metadata"]["status"] for item in sync_events} == {"completed", "failed"}
    query_events = [item for item in body["items"] if item["type"] == "query"]
    assert len(query_events) == 1
    item = query_events[0]
    assert item["summary"] == "Chat turn"
    assert item["metadata"] == {"event": "chat_turn", "conversation_id": str(conversation_id)}
    assert item["actor_id"] == str(staff["id"])
    dumped = json.dumps(item)
    assert prompt not in dumped
    assert "created_at" in item and "actor_id" in item
    assert "createdAt" not in item and "actorId" not in item
    for key in ("prompt", "query", "message", "body", "content", "text", "messages"):
        assert key not in item["metadata"]
    login_event = next(item for item in body["items"] if item["summary"] == "Login success")
    assert login_event["type"] == "system"
    assert login_event["actor_id"] == str(admin["id"])
    assert login_event["metadata"] == {"event": "login_success"}
    deny_event = next(item for item in body["items"] if item["summary"] == "Admin gate deny")
    assert deny_event["actor_id"] == str(staff["id"])
    assert deny_event["metadata"]["event"] == "admin_gate_deny"
    assert deny_event["metadata"]["path"].endswith("/access-level")


def test_type_query_param_filters_events(client, monkeypatch):
    install_store(monkeypatch)
    admin = account("admin")
    use_accounts(monkeypatch, admin)
    record_audit_event("sync_completed", metadata={"file_id": str(uuid4()), "status": "completed"})
    record_audit_event("chat_turn", metadata={"conversation_id": str(uuid4())})
    record_audit_event("login_success", actor_id=admin["id"])

    response = client.get("/admin/audit-events", headers=bearer(admin), params={"type": "query"})

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["type"] == "query"
    assert items[0]["summary"] == "Chat turn"


def test_cursor_paginates_by_created_at_then_id(client, monkeypatch):
    store = install_store(monkeypatch)
    admin = account("admin")
    use_accounts(monkeypatch, admin)
    older = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    newer = datetime(2026, 10, 2, 13, 0, tzinfo=timezone.utc)
    low_id = UUID(int=1)
    mid_id = UUID(int=2)
    high_id = UUID(int=3)
    store.rows.extend([
        {
            "id": low_id, "type": "system", "actor_id": None, "summary": "older-low",
            "metadata": {}, "created_at": older,
        },
        {
            "id": high_id, "type": "system", "actor_id": None, "summary": "older-high",
            "metadata": {}, "created_at": older,
        },
        {
            "id": mid_id, "type": "query", "actor_id": None, "summary": "newer",
            "metadata": {"conversation_id": None}, "created_at": newer,
        },
    ])

    headers = bearer(admin)
    seen = []
    cursor = None
    for _ in range(5):
        params = {"limit": 1}
        if cursor is not None:
            params["cursor"] = cursor
        response = client.get("/admin/audit-events", headers=headers, params=params)
        assert response.status_code == 200
        page = response.json()
        assert len(page["items"]) == 1
        seen.append(page["items"][0])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    else:
        raise AssertionError("pagination did not finish")

    assert [item["summary"] for item in seen] == ["newer", "older-high", "older-low"]
    assert len({item["id"] for item in seen}) == 3
    assert cursor is None

    invalid = client.get("/admin/audit-events", headers=headers, params={"cursor": "not-a-cursor"})
    assert invalid.status_code == 400


def test_first_chat_turn_records_the_created_conversation_id(monkeypatch):
    store = install_store(monkeypatch)
    prompt = "please-do-not-persist-this-user-message"
    owner_id = uuid4()
    conversation_id = _persist_new_chat(monkeypatch, owner_id, prompt)

    query_events = [row for row in store.rows if row["type"] == "query"]
    assert len(query_events) == 1
    assert query_events[0]["metadata"]["conversation_id"] == str(conversation_id)
    assert prompt not in json.dumps(query_events[0]["metadata"])
    assert set(query_events[0]["metadata"]) == {"event", "conversation_id"}


def test_record_is_fail_open(client, monkeypatch):
    def unavailable(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(audit_repository, "insert", unavailable)
    record_audit_event("login_success", actor_id=uuid4())

    admin = account("admin")
    monkeypatch.setattr(auth_routes, "authenticate", lambda email, password: admin)
    login = client.post("/auth/login", json={"email": admin["email"], "password": "x"})
    assert login.status_code == 200

    reached = []

    def create_exchange(**kwargs):
        reached.append(True)
        created_at = datetime.now(timezone.utc)
        return {
            "conversation": {
                "id": uuid4(), "owner_id": kwargs["owner_id"], "title": kwargs["title"],
                "created_at": created_at, "updated_at": created_at,
            },
            "messages": [
                {
                    "id": uuid4(), "role": "user", "content": kwargs["query"], "refused": False,
                    "citations": [], "status": "completed", "created_at": created_at,
                },
                {
                    "id": uuid4(), "role": "assistant", "content": kwargs["response"].answer,
                    "refused": False, "citations": [], "status": "completed", "created_at": created_at,
                },
            ],
        }

    monkeypatch.setattr(chat_service.chat_repository, "create_exchange", create_exchange)
    saved = chat_service.persist_response(
        "hello", uuid4(), ChatResponse(answer="ok", refused=False, citations=[]),
    )
    assert saved.conversation_id is not None
    assert reached == [True]

    staff = account("staff")
    use_accounts(monkeypatch, staff)
    denied = client.get("/admin/audit-events", headers=bearer(staff))
    assert denied.status_code == 403


def test_list_sql_keyset_orders_by_created_at_and_id(monkeypatch):
    captured = {}

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params=None):
            captured["sql"] = sql
            captured["params"] = params
            return self

        def fetchall(self):
            return []

    monkeypatch.setattr("app.audit.repository.get_connection", lambda: Connection())
    created_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    event_id = UUID(int=7)
    cursor = _encode_cursor({"created_at": created_at, "id": event_id})
    result = list_events("sync", 10, cursor)

    assert result == {"items": [], "next_cursor": None}
    assert "ORDER BY created_at DESC, id DESC" in captured["sql"]
    assert "(created_at, id) < (%s, %s)" in captured["sql"]
    assert "AND type = %s" in captured["sql"]
    assert captured["params"] == ("sync", created_at, event_id, 11)
