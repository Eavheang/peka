import threading

from fastapi.testclient import TestClient

from app.engine.indexing import worker
from app.auth.routes import authenticated
from app.main import app


def test_run_worker_stops_on_event(monkeypatch) -> None:
    processed = []

    class FakeJobsRepository:
        def claim_next(self):
            return None

        def reset_processing(self):
            processed.append("reset")

    monkeypatch.setattr(worker, "index_jobs_repository", FakeJobsRepository())
    stop = threading.Event()
    stop.set()
    worker.run_worker(stop)
    assert processed == ["reset"]


def test_index_status_reports_all_fields(monkeypatch) -> None:
    def fake_status(file_id):
        return {
            "id": file_id,
            "index_status": "failed",
            "index_attempts": 3,
            "index_error": "embedding endpoint down",
        }

    app.dependency_overrides[authenticated] = lambda: {"id": "u1", "role": "staff"}
    from app.files import routes as files_routes

    monkeypatch.setattr(files_routes.files_service, "get_index_status", fake_status)
    try:
        client = TestClient(app)
        response = client.get("/files/00000000-0000-0000-0000-000000000001/index-status")
        assert response.status_code == 200
        body = response.json()
        assert body == {
            "file_id": "00000000-0000-0000-0000-000000000001",
            "index_status": "failed",
            "index_attempts": 3,
            "index_error": "embedding endpoint down",
        }
    finally:
        app.dependency_overrides.clear()


def test_index_status_404_for_unknown_file(monkeypatch) -> None:
    app.dependency_overrides[authenticated] = lambda: {"id": "u1", "role": "staff"}
    from app.files import routes as files_routes

    monkeypatch.setattr(files_routes.files_service, "get_index_status", lambda file_id: None)
    try:
        client = TestClient(app)
        response = client.get("/files/00000000-0000-0000-0000-000000000002/index-status")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
