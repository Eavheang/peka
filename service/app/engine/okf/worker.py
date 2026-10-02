import json
import logging
import threading
import time
from app.audit.writer import record
from app.config import settings
from app.engine.source_extractor import source_id_for
from app.engine.chunks.chunker import parse_okf_chunks
from app.engine.chunks.embeddings import embed_chunks
from app.engine.chunks.repository import knowledge_chunks_repository
from app.engine.okf.converter import convert_to_okf
from app.engine.okf.job_repository import okf_jobs_repository


logger = logging.getLogger(__name__)


def process_next_job() -> bool:
    job = okf_jobs_repository.claim_next()
    if job is None:
        return False

    try:
        storage_root = settings.file_storage_dir.resolve()
        source = (storage_root / job["path"]).resolve()
        if not source.is_relative_to(storage_root):
            raise ValueError("Unsafe source path")
        extracted = storage_root / "extracted" / f"{source_id_for(source)}.json"
        extraction = json.loads(extracted.read_text(encoding="utf-8"))
        result = convert_to_okf(extraction, storage_root)
        chunks = parse_okf_chunks(result)
        vectors = embed_chunks(chunks)
        knowledge_chunks_repository.swap_active_set(job["file_id"], chunks, vectors)
    except Exception as error:
        logger.exception("OKF conversion failed for file %s", job["file_id"])
        status = okf_jobs_repository.fail(job["file_id"], str(error) or type(error).__name__)
        _record_sync_end(job["file_id"], status)
    else:
        okf_jobs_repository.complete(job["file_id"])
        _record_sync_end(job["file_id"], "completed")
    return True


def run_worker(stop: threading.Event | None = None) -> None:
    # ponytail: one worker serializes shared indexes; add per-organization locks before scaling.
    okf_jobs_repository.reset_processing()
    while stop is None or not stop.is_set():
        if not process_next_job():
            if stop is None:
                time.sleep(1)
            else:
                stop.wait(1)


def _record_sync_end(file_id, status: str) -> None:
    if status == "completed":
        summary = "Sync completed"
    elif status == "failed":
        summary = "Sync failed"
    else:
        return
    record("sync", summary, metadata={"file_id": str(file_id), "status": status})


if __name__ == "__main__":
    run_worker()
