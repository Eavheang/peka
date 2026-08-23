import threading

from fastapi.testclient import TestClient

from app.engine.okf import worker
from app.files import service as files_service
from app.files.routes import get_okf_status
from app.auth.routes import authenticated
from app.main import app


def test_run_worker_stops_on_event(monkeypatch) -> None:
    processed = []

    class FakeJobsRepository:
        def claim_next(self):
            return None

        def reset_processing(self):
            processed.append("reset")

    monkeypatch.setattr(worker, "okf_jobs_repository", FakeJobsRepository())
    stop = threading.Event()
    stop.set()
    worker.run_worker(stop)
    assert processed == ["reset"]


def test_worker_thread_helper_returns_joinable_thread() -> None:
    calls = []
    original = worker.run_worker
    monkeypatch_run = lambda *a: None  # noqa: E731
    worker.run_worker = lambda stop=None: calls.append(stop)  # type: ignore[method-assign]
    try:
        thread, stop = worker.run_worker_in_thread()
        stop.set()
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert len(calls) == 1
    finally:
        worker.run_worker = original  # type: ignore[method-assign]


def test_okf_status_reports_all_fields(monkeypatch) -> None:
    def fake_status(file_id):
        return {
            "id": file_id,
            "okf_status": "failed",
            "okf_attempts": 3,
            "okf_error": "embedding endpoint down",
        }

    app.dependency_overrides[authenticated] = lambda: {"id": "u1", "role": "staff"}
    from app.files import routes as files_routes

    monkeypatch.setattr(files_routes.files_service, "get_okf_status", fake_status)
    try:
        client = TestClient(app)
        response = client.get("/files/00000000-0000-0000-0000-000000000001/okf-status")
        assert response.status_code == 200
        body = response.json()
        assert body == {
            "file_id": "00000000-0000-0000-0000-000000000001",
            "okf_status": "failed",
            "okf_attempts": 3,
            "okf_error": "embedding endpoint down",
        }
    finally:
        app.dependency_overrides.clear()


def test_okf_status_404_for_unknown_file(monkeypatch) -> None:
    app.dependency_overrides[authenticated] = lambda: {"id": "u1", "role": "staff"}
    from app.files import routes as files_routes

    monkeypatch.setattr(files_routes.files_service, "get_okf_status", lambda file_id: None)
    try:
        client = TestClient(app)
        response = client.get("/files/00000000-0000-0000-0000-000000000002/okf-status")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
