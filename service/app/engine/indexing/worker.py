import json
import logging
import threading
import time

from app.audit.service import record_audit_event
from app.config import settings
from app.engine.source_extractor import source_id_for
from app.engine.chunks.chunker import CHUNKER_VERSION, chunk_extraction
from app.engine.chunks.embeddings import embed_chunks
from app.engine.chunks.repository import knowledge_chunks_repository
from app.engine.indexing.job_repository import index_jobs_repository


logger = logging.getLogger(__name__)


def process_next_job() -> bool:
    job = index_jobs_repository.claim_next()
    if job is None:
        return False

    try:
        storage_root = settings.file_storage_dir.resolve()
        source = (storage_root / job["path"]).resolve()
        if not source.is_relative_to(storage_root):
            raise ValueError("Unsafe source path")
        extracted = storage_root / "extracted" / f"{source_id_for(source)}.json"
        extraction = json.loads(extracted.read_text(encoding="utf-8"))
        chunks = chunk_extraction(extraction)
        vectors = embed_chunks(chunks)
        knowledge_chunks_repository.swap_active_set(job["file_id"], chunks, vectors)
    except Exception as error:
        logger.exception("Indexing failed for file %s", job["file_id"])
        status = index_jobs_repository.fail(job["file_id"], str(error) or type(error).__name__)
        if status == "failed":
            record_audit_event("sync_failed", metadata={"file_id": str(job["file_id"]), "status": status})
    else:
        index_jobs_repository.complete(job["file_id"])
        record_audit_event("sync_completed", metadata={"file_id": str(job["file_id"]), "status": "completed"})
    return True


def run_worker(stop: threading.Event | None = None) -> None:
    # ponytail: one worker serializes shared indexes; add per-organization locks before scaling.
    index_jobs_repository.reset_processing()
    index_jobs_repository.queue_outdated(CHUNKER_VERSION)
    while stop is None or not stop.is_set():
        if not process_next_job():
            if stop is None:
                time.sleep(1)
            else:
                stop.wait(1)


if __name__ == "__main__":
    run_worker()
