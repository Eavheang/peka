import json

from app.engine import source_extractor as extractor
from app.engine.indexing import worker


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


def _write_extraction(storage, relative_source, sections=None):
    source = storage / relative_source
    source.parent.mkdir(parents=True)
    source.write_text("source", encoding="utf-8")
    extraction_path = storage / "extracted" / f"{extractor.source_id_for(source)}.json"
    extraction_path.parent.mkdir()
    extraction_path.write_text(
        json.dumps(
            {
                "source_id": "source-1",
                "source_filename": "policy.pdf",
                "source_extension": ".pdf",
                "sections": [{"page": 7, "text": "Employees must sign in."}] if sections is None else sections,
            }
        ),
        encoding="utf-8",
    )


def _prepare(monkeypatch, tmp_path, *, sections=None):
    relative_source = "pdf/policy.pdf"
    _write_extraction(tmp_path, relative_source, sections)
    repository = FakeJobsRepository(relative_source)
    stored = []
    monkeypatch.setattr(worker, "index_jobs_repository", repository)
    monkeypatch.setattr(worker.settings, "file_storage_dir", tmp_path)
    monkeypatch.setattr(worker, "embed_chunks", lambda chunks: [[0.1] for _ in chunks])
    monkeypatch.setattr(
        worker,
        "knowledge_chunks_repository",
        type("Chunks", (), {"swap_active_set": lambda self, file_id, chunks, vectors: stored.append((file_id, chunks, vectors))})(),
    )
    return repository, stored


def test_indexes_source_text(monkeypatch, tmp_path):
    repository, stored = _prepare(monkeypatch, tmp_path)

    assert worker.process_next_job()

    assert repository.status == "completed"
    file_id, chunks, vectors = stored[0]
    assert file_id == "file-1"
    assert [(chunk.heading, chunk.content, chunk.source_locations) for chunk in chunks] == [
        ("Page 7", "Employees must sign in.", ({"page": 7},))
    ]
    assert vectors == [[0.1]]


def test_extraction_without_text_fails_the_job_clearly(monkeypatch, tmp_path):
    repository, stored = _prepare(monkeypatch, tmp_path, sections=[])

    assert all(worker.process_next_job() for _ in range(3))
    assert not worker.process_next_job()

    assert repository.status == "failed"
    assert repository.attempts == 3
    assert repository.error == "No text to index in policy.pdf"
    assert stored == []


def test_embed_failure_leaves_old_chunks_intact(monkeypatch, tmp_path):
    repository, stored = _prepare(monkeypatch, tmp_path)

    def embed_down(chunks):
        raise RuntimeError("embedding endpoint down")

    monkeypatch.setattr(worker, "embed_chunks", embed_down)

    worker.process_next_job()

    assert repository.status == "queued"
    assert repository.attempts == 1
    assert repository.error == "embedding endpoint down"
    assert stored == []
