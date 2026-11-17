"""Folder sync scheduling and token storage against a real PostgreSQL.

The time zone maths runs in SQL, so mocks cannot check it. Skipped unless TEST_DATABASE_URL points at a
database whose name contains "test"; see tests/test_search_database.py for the local setup.
"""
import os
import subprocess
import sys
from datetime import datetime, time, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import psycopg
import pytest

from app.config import settings
from app.google_drive.repository import google_drive_repository as repository

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="needs PostgreSQL: set TEST_DATABASE_URL")
SERVICE_DIR = Path(__file__).resolve().parents[1]


def execute(sql: str, *params):
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as connection:
        cursor = connection.execute(sql, params)
        return cursor.fetchone() if cursor.description else None


@pytest.fixture(scope="module")
def database():
    name = urlparse(TEST_DATABASE_URL).path.lstrip("/")
    assert "test" in name, "TEST_DATABASE_URL must point at a dedicated test database"
    original = settings.database_url
    settings.database_url = TEST_DATABASE_URL
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=SERVICE_DIR, env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
        check=True, capture_output=True,
    )
    execute("DELETE FROM google_drive_sync")
    yield
    execute("DELETE FROM google_drive_sync")
    settings.database_url = original


def create_user(role: str):
    return execute(
        "INSERT INTO users (email, display_name, password_hash, role) VALUES (%s, 'Sync', 'x', %s) RETURNING id",
        f"{uuid4().hex}@example.com", role,
    )[0]


def zone_at_noon() -> str:
    """A fixed-offset zone where it is now about 12:00, so 23:00 is later today and 01:00 is earlier."""
    offset = 12 - datetime.now(timezone.utc).hour
    return "Etc/GMT" if offset == 0 else f"Etc/GMT{'-' if offset > 0 else '+'}{abs(offset)}"


def test_runs_once_a_day_at_local_time_and_on_request(database):
    admin = create_user("admin")
    zone = zone_at_noon()
    repository.save_sync(admin, "folder-a", "A", "general", zone, time(23, 0))

    assert repository.is_due()
    job = repository.claim_due()  # a new folder is listed right away
    assert job["folder_id"] == "folder-a" and job["needs_baseline"]
    assert repository.find_sync()["run_requested"]  # until the run finishes, so the page keeps checking
    repository.finish_run("folder-a", "listed")
    assert not repository.is_due() and repository.claim_due() is None  # 23:00 local has not come yet

    repository.save_sync(admin, "folder-a", "A", "general", zone, time(1, 0))
    assert repository.claim_due() is not None  # 01:00 local has passed and today has not run
    assert repository.claim_due() is None  # once a day
    repository.save_sync(admin, "folder-a", "A", "confidential", zone, time(1, 0))
    assert repository.claim_due() is None  # editing anything but the time keeps today's run done

    assert repository.request_run()  # Sync now
    assert repository.claim_due() is not None
    repository.finish_run("folder-b", "an older folder's run")
    assert repository.find_sync()["run_requested"]  # only this folder's run clears its request
    repository.finish_run("folder-a", "done")
    assert repository.claim_due() is None

    execute("UPDATE users SET role = 'staff' WHERE id = %s", admin)
    assert repository.request_run()
    assert repository.claim_due()["owner_is_admin"] is False  # the run fails visibly instead of hanging


def test_changing_folder_forgets_synced_files_and_lists_again(database):
    admin = create_user("admin")
    repository.save_sync(admin, "folder-a", "A", "general", "UTC", time(0, 0))
    repository.save_baseline("folder-old", {"stale": "t0"})  # a run for a folder no longer synced
    assert repository.synced_files() == {}
    repository.save_baseline("folder-a", {"d1": "t1"})
    repository.record_synced("d2", None, "t2")
    assert execute("SELECT needs_baseline FROM google_drive_sync")[0] is False

    repository.save_sync(admin, "folder-a", "A", "confidential", "UTC", time(22, 0))
    assert set(repository.synced_files()) == {"d1", "d2"}

    other_admin = create_user("admin")
    repository.save_sync(other_admin, "folder-b", "B", "general", "UTC", time(22, 0))
    assert repository.synced_files() == {}
    assert execute("SELECT user_id, needs_baseline, run_requested FROM google_drive_sync") == (
        other_admin, True, True)

    repository.delete_sync()
    assert repository.find_sync() is None


def test_refresh_tokens_are_encrypted(database):
    user = create_user("staff")
    repository.save_refresh_token(user, "refresh-secret")
    stored = execute("SELECT refresh_token FROM google_drive_connections WHERE user_id = %s", user)[0]
    assert "refresh-secret" not in stored
    assert repository.find_refresh_token(user) == "refresh-secret"

    execute("UPDATE google_drive_connections SET refresh_token = 'plaintext' WHERE user_id = %s", user)
    assert repository.find_refresh_token(user) is None
