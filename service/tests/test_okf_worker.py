import json
import threading

from app.config import Settings
from app.engine import source_extractor as extractor
from app.engine.okf import converter, worker


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


def _prepare(monkeypatch, tmp_path, *, enrichment=False, sections=None):
    relative_source = "pdf/policy.pdf"
    _write_extraction(tmp_path, relative_source, sections)
    repository = FakeJobsRepository(relative_source)
    stored = []
    monkeypatch.setattr(worker, "okf_jobs_repository", repository)
    monkeypatch.setattr(worker.settings, "file_storage_dir", tmp_path)
    monkeypatch.setattr(worker.settings, "okf_enrichment_enabled", enrichment)
    monkeypatch.setattr(worker, "embed_chunks", lambda chunks: [[0.1] for _ in chunks])
    monkeypatch.setattr(
        worker,
        "knowledge_chunks_repository",
        type("Chunks", (), {"swap_active_set": lambda self, file_id, chunks, vectors: stored.append((file_id, chunks, vectors))})(),
    )
    return repository, stored


def test_enrichment_is_off_by_default():
    assert Settings.model_fields["okf_enrichment_enabled"].default is False


def test_default_path_indexes_source_text_without_calling_the_model(monkeypatch, tmp_path):
    repository, stored = _prepare(monkeypatch, tmp_path)
    model_calls = []
    # convert_to_okf stays real, so any route to the model ends here.
    monkeypatch.setattr(converter, "generate_structured", lambda *args, **kwargs: model_calls.append(args))
    submitted = []
    monkeypatch.setattr(worker._enrichment_pool, "submit", lambda *args: submitted.append(args))

    assert worker.process_next_job()

    assert repository.status == "completed"
    assert model_calls == []
    assert submitted == []
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


def test_enrichment_runs_after_activation_and_does_not_hold_the_queue(monkeypatch, tmp_path):
    repository, stored = _prepare(monkeypatch, tmp_path, enrichment=True)
    release, finished = threading.Event(), threading.Event()
    seen = []

    def convert(extraction, storage):
        seen.append((repository.status, len(stored), extraction["source_id"]))
        release.wait(5)
        finished.set()
        return {"files": []}

    monkeypatch.setattr(worker, "convert_to_okf", convert)

    # Returns while enrichment is still waiting: the next upload does not queue behind the model.
    assert worker.process_next_job()
    assert not finished.is_set()
    release.set()
    assert finished.wait(5)

    assert seen == [("completed", 1, "source-1")]
    assert len(stored) == 1


def test_enrichment_failure_keeps_the_file_indexed(monkeypatch, tmp_path):
    repository, stored = _prepare(monkeypatch, tmp_path, enrichment=True)
    called = []

    def convert(extraction, storage):
        called.append(extraction)
        raise RuntimeError("Context size has been exceeded")

    class ImmediatePool:
        def submit(self, function, *args):
            function(*args)

    monkeypatch.setattr(worker, "convert_to_okf", convert)
    monkeypatch.setattr(worker, "_enrichment_pool", ImmediatePool())

    assert worker.process_next_job()

    assert called
    assert repository.status == "completed"
    assert repository.error is None
    assert len(stored) == 1
