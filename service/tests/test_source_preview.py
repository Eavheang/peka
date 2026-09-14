from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth.routes import authenticated
from app.engine.search.repository import search_repository
from app.main import app


def test_source_preview_requires_auth():
    response = TestClient(app).post("/chat/source-preview", json={"title": "report.pdf", "heading": "Sales"})
    assert response.status_code in (401, 403)


@pytest.mark.parametrize("role,levels", [
    ("staff", ("general",)),
    ("admin", ("general", "confidential")),
])
@pytest.mark.parametrize("has_chunk_id", [True, False])
def test_preview_uses_current_permissions_and_returns_markdown(monkeypatch, role, levels, has_chunk_id):
    chunk_id = uuid4() if has_chunk_id else None
    calls = []

    def find_source(requested_id, title, heading, allowed_levels):
        calls.append((requested_id, title, heading, allowed_levels))
        return {"content": "## Sales\n\n**Revenue** increased.", "heading": "Sales"}

    monkeypatch.setattr(search_repository, "find_source", find_source)
    app.dependency_overrides[authenticated] = lambda: {"id": "u1", "role": role}
    try:
        response = TestClient(app).post("/chat/source-preview", json={
            "chunk_id": str(chunk_id) if chunk_id else None,
            "title": "report.pdf", "heading": "Sales",
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"content": "## Sales\n\n**Revenue** increased."}
    assert calls == [(chunk_id, "report.pdf", "Sales", levels)]


def test_missing_or_inaccessible_preview_is_not_found(monkeypatch):
    monkeypatch.setattr(search_repository, "find_source", lambda *args: None)
    app.dependency_overrides[authenticated] = lambda: {"id": "u1", "role": "staff"}
    try:
        response = TestClient(app).post("/chat/source-preview", json={"title": "report.pdf", "heading": "Sales"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404
