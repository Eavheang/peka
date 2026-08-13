import json

from app.engine import source_extractor as extractor
from app.engine.okf import worker


class FakeJobsRepository:
    def __init__(self, path: str):
        self.job = {"file_id": "file-1", "path": path}
        self.status = "queued"
        self.attempts = 0
        self.error = None

    def claim_next(self):
        if self.status != "queued" or self.attempts >= 3:
            return None
        self.status = "processing"
        self.attempts += 1
        return self.job

    def complete(self, file_id):
        self.status = "completed"
        self.error = None

    def fail(self, file_id, error):
        self.status = "failed" if self.attempts >= 3 else "queued"
        self.error = error
        return self.status


def _write_extraction(storage, relative_source):
    source = storage / relative_source
    source.parent.mkdir(parents=True)
    source.write_text("source", encoding="utf-8")
    extraction_path = storage / "extracted" / f"{extractor.source_id_for(source)}.json"
    extraction_path.parent.mkdir()
    extraction_path.write_text(json.dumps({"source_id": "source-1", "sections": []}), encoding="utf-8")


def test_worker_completes_one_queued_job(monkeypatch, tmp_path):
    relative_source = "pdf/policy.pdf"
    _write_extraction(tmp_path, relative_source)
    repository = FakeJobsRepository(relative_source)
    converted = []
    stored = []
    monkeypatch.setattr(worker, "okf_jobs_repository", repository)
    monkeypatch.setattr(
        worker,
        "knowledge_chunks_repository",
        type("Chunks", (), {"replace_for_file": lambda self, file_id, chunks, vectors: stored.append((file_id, chunks, vectors))})(),
    )
    monkeypatch.setattr(worker.settings, "file_storage_dir", tmp_path)
    monkeypatch.setattr(
        worker,
        "convert_to_okf",
        lambda extraction, storage: converted.append(extraction) or {"files": []},
    )
    monkeypatch.setattr(worker, "parse_okf_chunks", lambda result: ["chunk"])
    monkeypatch.setattr(worker, "embed_chunks", lambda chunks: [[0.1, 0.2]])

    assert worker.process_next_job()
    assert repository.status == "completed"
    assert converted[0]["source_id"] == "source-1"
    assert stored == [("file-1", ["chunk"], [[0.1, 0.2]])]


def test_worker_marks_job_failed_after_three_attempts(monkeypatch, tmp_path):
    relative_source = "pdf/policy.pdf"
    _write_extraction(tmp_path, relative_source)
    repository = FakeJobsRepository(relative_source)
    monkeypatch.setattr(worker, "okf_jobs_repository", repository)
    monkeypatch.setattr(
        worker,
        "knowledge_chunks_repository",
        type("Chunks", (), {"replace_for_file": lambda *args: None})(),
    )
    monkeypatch.setattr(worker.settings, "file_storage_dir", tmp_path)
    monkeypatch.setattr(
        worker,
        "convert_to_okf",
        lambda extraction, storage: (_ for _ in ()).throw(RuntimeError("llama unavailable")),
    )

    assert all(worker.process_next_job() for _ in range(3))
    assert not worker.process_next_job()
    assert repository.status == "failed"
    assert repository.attempts == 3
    assert repository.error == "llama unavailable"
