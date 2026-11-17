"""Re-extract every stored file and queue it for indexing. Run inside the service container: python /tmp/reindex.py"""
import json
from pathlib import Path

from app.config import settings
from app.database import get_connection
from app.engine.source_extractor import extract_file

root = settings.file_storage_dir.resolve()
with get_connection() as connection:
    for row in connection.execute("SELECT id, path FROM files").fetchall():
        extraction = extract_file(root / row["path"])
        (root / "extracted" / f"{extraction['source_id']}.json").write_text(json.dumps(extraction, indent=2) + "\n")
    connection.execute("UPDATE index_jobs SET status = 'queued', attempts = 0, last_error = NULL")
print("queued")
