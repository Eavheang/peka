"""Measurements behind notes.md. Writes to DATABASE_URL, so point it at a throwaway copy.

Run from service/ with the old query saved from before migration 021:
    git show 66a6d2c:service/app/engine/search/repository.py > /tmp/old_repository.py
    python ../eval/results-perf/2026-11-07-search-indexes/measure.py compare /tmp/old_repository.py
    python ../eval/results-perf/2026-11-07-search-indexes/measure.py grow 240
    python ../eval/results-perf/2026-11-07-search-indexes/measure.py compare /tmp/old_repository.py 3
    python ../eval/results-perf/2026-11-07-search-indexes/measure.py ann
"""
import importlib.util
import json
import pathlib
import random
import re
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, ".")
import httpx
import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from app.config import settings
from app.engine.chunks.chunker import passage_text
from app.engine.search.repository import search_repository
from app.engine.search.service import embed_query, rerank

assert "copy" in settings.database_url or "eval" in settings.database_url, "use a throwaway database"
LEVELS = {"staff": ("general",), "full": ("general", "confidential")}
EVAL = pathlib.Path("../eval")
HNSW = "CREATE INDEX knowledge_chunks_embedding_idx ON knowledge_chunks USING hnsw (embedding vector_cosine_ops) WITH (m = 32, ef_construction = 200)"


def connect():
    connection = psycopg.connect(settings.database_url, row_factory=dict_row, autocommit=True)
    register_vector(connection)
    return connection


def questions():
    rows = [json.loads(line) for line in (EVAL / "questions.jsonl").read_text().splitlines() if line.strip()]
    rows += json.loads((EVAL / "question-2.json").read_text())
    return [row for row in rows if not row.get("unanswerable")]


def stems(question):
    files = question.get("file")
    return [pathlib.Path(name).stem.lower() for name in (files if isinstance(files, list) else [files] if files else [])]


def compare(old_path, every="1"):
    spec = importlib.util.spec_from_file_location("old_repository", old_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with connect() as connection:
        indexed = {pathlib.Path(r["path"]).stem.lower() for r in connection.execute("SELECT path FROM files").fetchall()}
        print("chunks", connection.execute("SELECT count(*) AS n FROM knowledge_chunks").fetchone()["n"])
    labelled = [q for q in questions() if any(s in indexed for s in stems(q))][:: int(every)]
    hits = {"old": [0, 0, 0], "new": [0, 0, 0]}
    times = {name: {"old": [], "new": []} for name in LEVELS}
    for question in labelled:
        text, vector = question["question"], embed_query(question["question"])
        for name, levels in LEVELS.items():
            for label, repository in (("old", module.search_repository), ("new", search_repository)):
                started = time.perf_counter()
                rows = repository.search_chunks(vector, levels, top_k=20, query_text=text)
                times[name][label].append(time.perf_counter() - started)
                if name == "full":
                    found = [row["stem"].lower() for row in rerank(text, rows)]
                    for slot, k in enumerate((1, 5, 10)):
                        hits[label][slot] += any(s in f for f in found[:k] for s in stems(question))
    print("labelled", len(labelled), "recall@1/5/10", hits)
    for name, runs in times.items():
        print(name, {label: round(1000 * statistics.median(values)) for label, values in runs.items()}, "ms median")


def grow(seconds):
    random.seed(11)
    url = settings.embedding_base_url.rstrip("/") + "/embeddings"

    def embed(text):
        reply = httpx.post(url, json={"model": settings.embedding_model, "input": text[:1200]}, timeout=120)
        reply.raise_for_status()
        return reply.json()["data"][0]["embedding"]

    with connect() as connection:
        real = connection.execute("SELECT heading, content FROM knowledge_chunks").fetchall()
        user = connection.execute("SELECT id FROM users LIMIT 1").fetchone()["id"]
        sentences = [s.strip() for r in real for s in re.split(r"(?<=[.!?])\s+|\n+", r["content"]) if len(s.strip()) > 25]
        headings = [r["heading"] for r in real]
        words = sorted({w for s in sentences for w in re.findall(r"[A-Za-z]{5,}", s)})
        documents, count, started = {}, 0, time.time()
        with ThreadPoolExecutor(8) as pool:
            while time.time() - started < float(seconds):
                batch = []
                for _ in range(32):
                    text = " ".join(random.sample(sentences, 4) + random.sample(words, 3))
                    batch.append((f"gen-report-{count // 20}", random.choice(headings), text))
                    count += 1
                vectors = pool.map(embed, [passage_text(*row) for row in batch])
                for (document, heading, text), vector in zip(batch, vectors):
                    documents.setdefault(document, []).append((heading, text, Vector(vector)))
        connection.execute("DROP INDEX knowledge_chunks_embedding_idx")
        with connection.transaction(), connection.cursor() as cursor:
            for number, (document, rows) in enumerate(documents.items()):
                level = "confidential" if number % 2 else "general"
                for extension in ("pdf", "docx", "md"):  # identical vectors: the hardest kind of format copy
                    path = f"gen/{document}.{extension}"
                    file_id = cursor.execute(
                        "INSERT INTO files (path, content_type, sha256, author_id, access_level) "
                        "VALUES (%s, 'text/plain', %s, %s, %s) RETURNING id",
                        (path, path, user, level),
                    ).fetchone()["id"]
                    set_id = cursor.execute(
                        "INSERT INTO chunk_sets (file_id, status) VALUES (%s, 'active') RETURNING id", (file_id,)
                    ).fetchone()["id"]
                    cursor.executemany(
                        "INSERT INTO knowledge_chunks (file_id, file_path, chunk_set_id, heading, content, embedding) "
                        "VALUES (%s, %s, %s, %s, %s, %s)",
                        [(file_id, path, set_id, *row) for row in rows],
                    )
                    cursor.execute(
                        "UPDATE chunk_sets SET centroid = (SELECT avg(embedding) FROM knowledge_chunks "
                        "WHERE chunk_set_id = %s) WHERE id = %s",
                        (set_id, set_id),
                    )
        started = time.time()
        connection.execute(HNSW)
        print("hnsw build s", round(time.time() - started, 1))
        connection.execute("ANALYZE")
        print(connection.execute(
            "SELECT count(*) AS chunks, pg_size_pretty(pg_relation_size('knowledge_chunks_embedding_idx')) AS hnsw, "
            "pg_size_pretty(pg_relation_size('knowledge_chunks_search_words_idx')) AS gin FROM knowledge_chunks"
        ).fetchone())


def ann():
    """Recall of the whole search query with the HNSW index against the same query without it."""
    texts = [q["question"] for q in questions()][::3]
    vectors = [embed_query(text) for text in texts]

    def run(levels):
        rows, times = [], []
        for text, vector in zip(texts, vectors):
            started = time.perf_counter()
            rows.append(search_repository.search_chunks(vector, levels, top_k=20, query_text=text))
            times.append(time.perf_counter() - started)
        return rows, 1000 * statistics.median(times)

    with connect() as connection:
        with_index = {name: run(levels) for name, levels in LEVELS.items()}
        connection.execute("DROP INDEX knowledge_chunks_embedding_idx")
        without = {name: run(levels) for name, levels in LEVELS.items()}
        connection.execute(HNSW)
        connection.execute("ANALYZE")
    for name in LEVELS:
        shares = []
        for a, b in zip(without[name][0], with_index[name][0]):
            exact = {(r["stem"], r["heading"], r["content"]) for r in a}
            shares.append(len(exact & {(r["stem"], r["heading"], r["content"]) for r in b}) / max(1, len(exact)))
        print(name, "questions", len(shares), "top-20 overlap", round(statistics.mean(shares), 3), "lowest", round(min(shares), 3),
              "ms with", round(with_index[name][1]), "ms without", round(without[name][1]))
    source = pathlib.Path("app/engine/search/repository.py").read_text()
    sql = re.search(r'r"""\n(.*?)"""', source, re.S).group(1)
    for name, levels in LEVELS.items():
        with connect() as connection, connection.transaction():
            connection.execute("SET LOCAL hnsw.iterative_scan = strict_order")
            connection.execute("SELECT set_config('hnsw.ef_search', '1000', true)")
            plan = connection.execute("EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF) " + sql, {
                "levels": list(levels), "text": texts[0], "vector": Vector(vectors[0]),
                "floor": settings.search_similarity_floor, "candidates": 480, "pool": 80, "same_document": 0.85, "limit": 20,
            }).fetchall()
        print("plan", name)
        for row in plan:
            print(re.sub(r"'\[[^\]]*\]'::vector", "'[query]'", row["QUERY PLAN"])[:150])


{"compare": compare, "grow": grow, "ann": ann}[sys.argv[1]](*sys.argv[2:])
