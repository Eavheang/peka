import json
import logging
import time

from app.config import settings
from app.engine.extractor import source_id_for
from app.engine.chunked.chunker import parse_okf_chunks
from app.engine.chunked.embeddings import embed_chunks
from app.engine.chunked.repository import knowledge_chunks_repository
from app.engine.OKFExtractor.main import convert_to_okf
from app.engine.OKFExtractor.repository import okf_jobs_repository


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
        knowledge_chunks_repository.replace_for_file(job["file_id"], chunks, vectors)
    except Exception as error:
        logger.exception("OKF conversion failed for file %s", job["file_id"])
        okf_jobs_repository.fail(job["file_id"], str(error) or type(error).__name__)
    else:
        okf_jobs_repository.complete(job["file_id"])
    return True


def run_worker() -> None:
    # ponytail: one worker serializes shared indexes; add per-organization locks before scaling.
    okf_jobs_repository.reset_processing()
    while True:
        if not process_next_job():
            time.sleep(1)


if __name__ == "__main__":
    run_worker()
