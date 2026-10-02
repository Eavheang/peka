import asyncio
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.audit.repository import audit_repository
from app.audit.writer import record
from app.auth import routes as auth_routes
from app.auth.security import create_access_token
from app.chat import service as chat_service
from app.engine.okf.job_repository import okf_jobs_repository


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


class _JobResult:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _JobConnection:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        if self.status is None:
            return _JobResult(None)
        return _JobResult({"status": self.status})


def install_store(monkeypatch):
    store = MemoryAuditStore()
    monkeypatch.setattr(audit_repository, "insert", store.insert)
    monkeypatch.setattr(audit_repository, "_fetch", store.fetch)
    return store


def test_staff_cannot_list_audit_events(client, monkeypatch):
    install_store(monkeypatch)
    staff = account("staff")
    use_accounts(monkeypatch, staff)

    response = client.get("/admin/audit-events", headers=bearer(staff))

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin role required"


def test_admin_list_includes_sync_query_login_and_admin_deny(client, monkeypatch):
    install_store(monkeypatch)
    admin = account("admin")
    staff = account("staff")
    use_accounts(monkeypatch, admin, staff)
    job_status = {"status": "completed"}
    monkeypatch.setattr(
        "app.engine.okf.job_repository.get_connection",
        lambda: _JobConnection(job_status["status"]),
    )
    prompt = "super-secret-prompt-body-should-not-be-stored"
    conversation_id = uuid4()

    def stop_after_audit(*args, **kwargs):
        raise RuntimeError("stop after audit")

    monkeypatch.setattr(chat_service, "_search_plan", stop_after_audit)
    file_id = uuid4()
    okf_jobs_repository.complete(file_id)
    job_status["status"] = "queued"
    assert okf_jobs_repository.fail(file_id, "transient") == "queued"
    job_status["status"] = "failed"
    assert okf_jobs_repository.fail(file_id, "terminal") == "failed"
    try:
        chat_service.answer_from_knowledge(
            prompt, "staff", conversation_id=conversation_id, actor_id=staff["id"],
        )
    except RuntimeError:
        pass

    async def read_stream():
        async for _event in chat_service.stream_answer_from_knowledge(
            prompt, "staff", conversation_id=conversation_id, actor_id=staff["id"],
        ):
            pass

    try:
        asyncio.run(read_stream())
    except RuntimeError:
        pass

    monkeypatch.setattr(auth_routes, "authenticate", lambda email, password: admin)
    login = client.post("/auth/login", json={"email": admin["email"], "password": "x"})
    assert login.status_code == 200
    denied = client.get("/auth/users", headers=bearer(staff))
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
    assert all(set(item["metadata"]) == {"file_id", "status"} for item in sync_events)
    assert {item["metadata"]["status"] for item in sync_events} == {"completed", "failed"}
    query_events = [item for item in body["items"] if item["type"] == "query"]
    assert query_events
    for item in query_events:
        assert item["summary"] == "Chat turn"
        assert set(item["metadata"]) == {"conversation_id"}
        assert item["metadata"]["conversation_id"] == str(conversation_id)
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
    deny_event = next(item for item in body["items"] if item["summary"] == "Admin gate deny")
    assert deny_event["actor_id"] == str(staff["id"])
    assert deny_event["metadata"]["path"] == "/auth/users"


def test_type_query_param_filters_events(client, monkeypatch):
    install_store(monkeypatch)
    admin = account("admin")
    use_accounts(monkeypatch, admin)
    record("sync", "Sync completed", metadata={"file_id": str(uuid4()), "status": "completed"})
    record("query", "Chat turn", metadata={"conversation_id": str(uuid4())})
    record("system", "Login success", actor_id=admin["id"])

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


def test_query_audit_does_not_store_prompt_or_message_body(client, monkeypatch):
    install_store(monkeypatch)
    admin = account("admin")
    use_accounts(monkeypatch, admin)
    prompt = "please-do-not-persist-this-user-message"
    conversation_id = uuid4()

    def stop_after_audit(*args, **kwargs):
        raise RuntimeError("stop after audit")

    monkeypatch.setattr(chat_service, "_search_plan", stop_after_audit)
    try:
        chat_service.answer_from_knowledge(prompt, "admin", conversation_id=conversation_id, actor_id=admin["id"])
    except RuntimeError:
        pass

    response = client.get("/admin/audit-events", headers=bearer(admin), params={"type": "query"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    dumped = json.dumps(items[0])
    assert prompt not in dumped
    assert set(items[0]["metadata"]) == {"conversation_id"}
    assert items[0]["summary"] == "Chat turn"


def test_record_is_fail_open(client, monkeypatch):
    def unavailable(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(audit_repository, "insert", unavailable)
    record("system", "Login success", actor_id=uuid4())

    admin = account("admin")
    monkeypatch.setattr(auth_routes, "authenticate", lambda email, password: admin)
    login = client.post("/auth/login", json={"email": admin["email"], "password": "x"})
    assert login.status_code == 200

    reached = []

    def stop_after_audit(*args, **kwargs):
        reached.append(True)
        raise RuntimeError("llm")

    monkeypatch.setattr(chat_service, "_search_plan", stop_after_audit)
    try:
        chat_service.answer_from_knowledge("hello", "staff")
    except RuntimeError as error:
        assert str(error) == "llm"
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
    from app.audit.repository import _encode_cursor

    cursor = _encode_cursor({"created_at": created_at, "id": event_id})
    result = audit_repository.list_events("sync", 10, cursor)

    assert result == {"items": [], "next_cursor": None}
    assert "ORDER BY created_at DESC, id DESC" in captured["sql"]
    assert "(created_at, id) < (%s, %s)" in captured["sql"]
    assert "AND type = %s" in captured["sql"]
    assert captured["params"] == ( "sync", created_at, event_id, 11)
