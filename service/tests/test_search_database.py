"""Role-based access in the search SQL, tested against a real PostgreSQL with pgvector.

The other tests mock the database, so the `access_level = ANY(...)` filters were never run against
real SQL. These use the real repositories and a dedicated database, and are skipped unless
TEST_DATABASE_URL points at one (its name must contain "test"). Locally:

    docker compose exec postgres psql -U peka -d postgres -c "CREATE DATABASE peka_test"
    TEST_DATABASE_URL=postgresql://peka:peka_dev_password@postgres:5432/peka_test python -m pytest
"""
import math
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import psycopg
import pytest

from app.config import settings
from app.engine.chunks.chunker import OKFChunk
from app.engine.chunks.repository import knowledge_chunks_repository
from app.engine.search import service as search_service
from app.engine.search.repository import search_repository
from app.files.repository import files_repository

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="needs a PostgreSQL with pgvector: set TEST_DATABASE_URL"
)
SERVICE_DIR = Path(__file__).resolve().parents[1]


def unit_vector(*weights: float) -> list[float]:
    vector = [0.0] * settings.embedding_dimensions
    vector[: len(weights)] = weights
    norm = math.sqrt(sum(w * w for w in vector))
    return [w / norm for w in vector]


# The query is closer to the confidential chunk (cosine 0.8) than to the general one (0.6); both
# are above the similarity floor, so only the access filter can keep the closer one out.
QUERY = unit_vector(0.6, 0.8)


def execute(sql: str, *params):
    """Run one statement on the test database, committed; returns the first row if it has one."""
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as connection:
        cursor = connection.execute(sql, params)
        return cursor.fetchone() if cursor.description else None


@pytest.fixture(scope="module")
def database():
    name = urlparse(TEST_DATABASE_URL).path.lstrip("/")
    assert "test" in name, "TEST_DATABASE_URL must point at a dedicated test database"
    original = settings.database_url
    settings.database_url = TEST_DATABASE_URL  # the repositories connect through settings
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=SERVICE_DIR, env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
        check=True, capture_output=True,
    )
    yield
    settings.database_url = original


@pytest.fixture(scope="module")
def corpus(database):
    run = uuid4().hex[:8]
    user_id = execute(
        "INSERT INTO users (email, password_hash, role) VALUES (%s, 'x', 'admin') RETURNING id",
        f"role-filter-{run}@example.test",
    )[0]
    general, secret, expenses = files_repository.create_many(
        [
            (f"role-filter/{run}-handbook.txt", "text/plain", f"sha-general-{run}", "general"),
            (f"role-filter/{run}-salaries.txt", "text/plain", f"sha-secret-{run}", "confidential"),
            (f"role-filter/{run}-expenses.txt", "text/plain", f"sha-expenses-{run}", "general"),
        ],
        user_id,
    )
    for file, heading, content, vector in (
        (general, "Leave policy", "Every employee gets 20 days of leave.", unit_vector(1, 0)),
        (secret, "Pay bands", "Senior engineers earn between 90k and 120k.", unit_vector(0, 1)),
        # A second general chunk: staff's reranker request should hold every row they may see.
        (expenses, "Receipts", "Receipts are required above 50 dollars.", unit_vector(1, 0)),
    ):
        chunk = OKFChunk(title=file["path"], heading=heading, content=content, source_locations=({"page": 1},))
        knowledge_chunks_repository.swap_active_set(file["id"], [chunk], [vector])
    yield SimpleNamespace(general=general, secret=secret, run=run)
    ids = [general["id"], secret["id"], expenses["id"]]
    for table in ("knowledge_chunks", "chunk_sets", "okf_jobs", "files"):
        column = "id" if table == "files" else "file_id"
        execute(f"DELETE FROM {table} WHERE {column} = ANY(%s)", ids)
    execute("DELETE FROM users WHERE id = %s", user_id)


def found(results, corpus) -> set[str]:
    """Which of this module's two files appear in the results (other data in the DB is ignored)."""
    ours = {str(corpus.general["id"]): "general", str(corpus.secret["id"]): "confidential"}
    return {ours[str(row["file_id"])] for row in results if str(row["file_id"]) in ours}


def test_general_only_search_never_returns_the_closer_confidential_chunk(corpus):
    results = search_repository.search_chunks(QUERY, ("general",), top_k=10)

    assert found(results, corpus) == {"general"}


def test_full_access_search_returns_both_with_the_closer_confidential_chunk_first(corpus):
    results = search_repository.search_chunks(QUERY, ("general", "confidential"), top_k=10)
    ours = {str(corpus.general["id"]): "general", str(corpus.secret["id"]): "confidential"}

    assert [ours[str(r["file_id"])] for r in results if str(r["file_id"]) in ours] == [
        "confidential", "general"]


@pytest.mark.parametrize(
    "role, expected",
    [("staff", {"general"}), ("senior", {"general", "confidential"}),
     ("admin", {"general", "confidential"}), ("unknown-role", {"general"})],
)
def test_search_knowledge_applies_the_role_mapping_end_to_end(monkeypatch, corpus, role, expected):
    monkeypatch.setattr(search_service, "embed_query", lambda query: QUERY)

    results = search_service.search_knowledge("what are the rules?", role)

    assert found(results, corpus) == expected


@pytest.mark.parametrize("role, sees_secret", [("staff", False), ("admin", True)])
def test_reranker_only_receives_rows_the_role_may_see(monkeypatch, corpus, role, sees_secret):
    monkeypatch.setattr(search_service, "embed_query", lambda query: QUERY)
    sent = []

    def post(url, **kwargs):
        sent.extend(kwargs["json"]["texts"])
        ranks = [{"index": index, "score": 0.0} for index in range(len(sent))]
        return httpx.Response(200, json=ranks, request=httpx.Request("POST", url))

    monkeypatch.setattr(search_service.httpx, "post", post)

    search_service.search_knowledge("what are the rules?", role)

    passages = "\n".join(sent)
    assert "Every employee gets 20 days" in passages and "Receipts are required" in passages
    assert ("Senior engineers" in passages) is sees_secret


def test_one_format_of_a_document_keeps_all_its_sections_and_hides_its_copies(database):
    run = uuid4().hex[:8]
    user_id = execute(
        "INSERT INTO users (email, password_hash, role) VALUES (%s, 'x', 'admin') RETURNING id",
        f"formats-{run}@example.test",
    )[0]
    pdf, docx = files_repository.create_many(
        [
            (f"formats/{run}-report.pdf", "application/pdf", f"sha-pdf-{run}", "general"),
            (f"formats/{run}-report.docx", "application/octet-stream", f"sha-docx-{run}", "general"),
        ],
        user_id,
    )
    try:
        for file, heading, vector in ((pdf, "Page 1", unit_vector(0.6, 0.8)), (docx, "Costs", unit_vector(1, 0.6))):
            chunks = [OKFChunk(file["path"], heading, f"Fact {part}.", ()) for part in (1, 2)]
            knowledge_chunks_repository.swap_active_set(file["id"], chunks, [vector, vector])

        results = search_repository.search_chunks(QUERY, ("general",), top_k=10)

        ours = [row for row in results if row["stem"] == f"{run}-report"]
        assert [row["heading"] for row in ours] == ["Page 1", "Page 1"]
        assert {row["content"] for row in ours} == {"Fact 1.", "Fact 2."}
    finally:
        ids = [pdf["id"], docx["id"]]
        for table in ("knowledge_chunks", "chunk_sets", "okf_jobs", "files"):
            execute(f"DELETE FROM {table} WHERE {'id' if table == 'files' else 'file_id'} = ANY(%s)", ids)
        execute("DELETE FROM users WHERE id = %s", user_id)


def test_changing_a_file_to_confidential_hides_it_from_staff_immediately(corpus):
    files_repository.update_access_level(corpus.general["id"], "confidential")
    try:
        assert found(search_repository.search_chunks(QUERY, ("general",), top_k=10), corpus) == set()
        assert found(search_repository.search_chunks(QUERY, ("general", "confidential"), top_k=10), corpus) == {
            "general", "confidential"}
    finally:
        files_repository.update_access_level(corpus.general["id"], "general")
    assert found(search_repository.search_chunks(QUERY, ("general",), top_k=10), corpus) == {"general"}


def test_only_active_chunk_sets_are_searchable(corpus):
    execute("UPDATE chunk_sets SET status = 'superseded' WHERE file_id = %s", corpus.general["id"])
    try:
        assert found(search_repository.search_chunks(QUERY, ("general", "confidential"), top_k=10), corpus) == {
            "confidential"}
    finally:
        execute("UPDATE chunk_sets SET status = 'active' WHERE file_id = %s", corpus.general["id"])


def test_source_preview_lookup_respects_access_level(corpus):
    general_title, secret_title = f"{corpus.run}-handbook.txt", f"{corpus.run}-salaries.txt"

    assert search_repository.find_source(None, general_title, "Leave policy", ("general",)) is not None
    assert search_repository.find_source(None, secret_title, "Pay bands", ("general",)) is None
    preview = search_repository.find_source(None, secret_title, "Pay bands", ("general", "confidential"))
    assert preview is not None and "Senior engineers" in preview["content"]


def test_file_listing_hides_confidential_files_from_general_only_roles(corpus):
    def listed(levels):
        return {str(f["id"]) for f in files_repository.list_all(levels)}

    ids = {str(corpus.general["id"]), str(corpus.secret["id"])}
    assert listed(("general",)) & ids == {str(corpus.general["id"])}
    assert listed(("general", "confidential")) & ids == ids


def test_keyword_match_finds_a_chunk_the_vector_search_misses(corpus):
    unrelated = unit_vector(0, 0, 1)  # cosine 0 with both chunks: below the similarity floor

    assert found(search_repository.search_chunks(unrelated, ("general",), top_k=10), corpus) == set()
    assert found(
        search_repository.search_chunks(unrelated, ("general",), top_k=10, query_text="how many days of leave?"), corpus
    ) == {"general"}


def test_keyword_match_finds_a_chunk_by_its_file_name_and_returns_the_title(corpus):
    unrelated = unit_vector(0, 0, 1)  # below the similarity floor, so only the keyword search can match

    results = search_repository.search_chunks(unrelated, ("general",), top_k=10, query_text="handbook")

    assert found(results, corpus) == {"general"}
    assert next(row for row in results if row["file_id"] == corpus.general["id"])["file_path"] == corpus.general["path"]


def test_file_name_match_does_not_reveal_a_confidential_file_to_general_roles(corpus):
    unrelated = unit_vector(0, 0, 1)

    assert found(search_repository.search_chunks(unrelated, ("general",), top_k=10, query_text="salaries"), corpus) == set()
    assert found(
        search_repository.search_chunks(unrelated, ("general", "confidential"), top_k=10, query_text="salaries"), corpus
    ) == {"confidential"}


def index_file(path, access_level, user_id, sections):
    file = files_repository.create_many([(path, "text/plain", f"sha-{path}", access_level)], user_id)[0]
    chunks = [
        OKFChunk(title=path, heading=heading, content=f"{heading} text.", source_locations=({"page": 1},))
        for heading, _ in sections
    ]
    knowledge_chunks_repository.swap_active_set(file["id"], chunks, [vector for _, vector in sections])
    return file


@pytest.fixture
def owner(database):
    user_id = execute(
        "INSERT INTO users (email, password_hash, role) VALUES (%s, 'x', 'admin') RETURNING id",
        f"copies-{uuid4().hex[:8]}@example.test",
    )[0]
    files = []
    yield SimpleNamespace(id=user_id, files=files)
    ids = [file["id"] for file in files]
    for table in ("knowledge_chunks", "chunk_sets", "okf_jobs", "files"):
        execute(f"DELETE FROM {table} WHERE {'id' if table == 'files' else 'file_id'} = ANY(%s)", ids)
    execute("DELETE FROM users WHERE id = %s", user_id)


def test_files_sharing_a_name_but_not_a_subject_both_stay_in_results(owner):
    run = uuid4().hex[:8]
    owner.files += [
        index_file(f"pdf/{run}-budget.pdf", "general", owner.id, [("Spending", unit_vector(1, 0))]),
        index_file(f"xlsx/{run}-budget.xlsx", "general", owner.id, [("Travel", unit_vector(1, 1))]),
    ]

    stems = [row for row in search_repository.search_chunks(QUERY, ("general",), top_k=10) if run in row["stem"]]

    assert {row["heading"] for row in stems} == {"Spending", "Travel"}


def test_copies_whose_names_differ_only_by_case_collapse(owner):
    run = uuid4().hex[:8]
    owner.files += [
        index_file(f"pdf/{run}-Report.pdf", "general", owner.id, [("Summary", unit_vector(1, 0))]),
        index_file(f"docx/{run}-report.docx", "general", owner.id, [("Summary", unit_vector(1, 0))]),
    ]

    results = search_repository.search_chunks(QUERY, ("general",), top_k=10)

    assert len([row for row in results if run in row["stem"]]) == 1


def test_format_copies_do_not_crowd_another_document_out_of_the_pool(owner):
    run = uuid4().hex[:8]
    sections = [(f"Section {index}", unit_vector(1, 0.01 * index)) for index in range(10)]
    owner.files += [
        index_file(f"{ext}/{run}-guide.{ext}", "general", owner.id, sections)
        for ext in ("pdf", "docx", "md", "txt", "pptx", "xlsx")
    ]
    owner.files.append(
        index_file(f"txt/{run}-other.txt", "general", owner.id, [("Other", unit_vector(1, -0.2))])
    )

    # 6 copies of 10 sections rank above "Other": 60 rows, more than the 56 rows the top 14 results keep.
    results = search_repository.search_chunks(QUERY, ("general",), top_k=14)

    assert "Other" in {row["heading"] for row in results}
