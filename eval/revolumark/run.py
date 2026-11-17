"""RevoluMark eval: retrieval (POST /search) and answers (POST /chat/stream) against a running PEKA.

Usage: python3 run.py search|chat [set]   (set "holdout" reads questions_holdout.jsonl; results get the same suffix)
Reads ADMIN_EMAIL / ADMIN_PASSWORD from service/.env.
"""
import json
import re
import statistics
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
API = "http://localhost:8000"
ENV = dict(
    line.split("=", 1) for line in (HERE.parents[1] / "service/.env").read_text().splitlines()
    if line.startswith(("ADMIN_EMAIL=", "ADMIN_PASSWORD="))
)


def post(path, body, token=None, timeout=300):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.urlopen(
        urllib.request.Request(API + path, json.dumps(body).encode(), headers), timeout=timeout
    )


def login():
    with post("/auth/login", {"email": ENV["ADMIN_EMAIL"], "password": ENV["ADMIN_PASSWORD"]}) as r:
        return json.load(r)["access_token"]


def doc_id(title):
    m = re.match(r"(\d\d)_", Path(title).name)
    return m.group(1) if m else title


def norm(text):
    return text.lower().replace(",", "").replace("–", "-").replace("—", "-").replace("−", "-")


def keys_hit(answer, keys):
    a = norm(answer)
    return sum(any(alt in a for alt in group) for group in keys)


suffix = f"_{sys.argv[2]}" if len(sys.argv) > 2 else ""
questions = [json.loads(line) for line in (HERE / f"questions{suffix}.jsonl").read_text().splitlines() if line.strip()]
mode = sys.argv[1]
token = login()

if mode == "search":
    out, rows = (HERE / f"search_results{suffix}.jsonl").open("w"), []
    for q in questions:
        t = time.monotonic()
        with post("/search", {"query": q["q"]}, token) as r:
            results = json.load(r)
        ms = (time.monotonic() - t) * 1000
        ranked = [doc_id(x["title"]) for x in results]
        rank = next((i + 1 for i, d in enumerate(ranked) if d in q["docs"]), None)
        row = {"id": q["id"], "type": q["type"], "rank": rank, "ranked": ranked, "ms": round(ms),
               "top_score": results[0]["score"] if results else None}
        rows.append(row)
        out.write(json.dumps(row) + "\n")
    ans = [r for r in rows if r["type"] != "U"]
    for k in (1, 3, 5, 10):
        hit = sum(1 for r in ans if r["rank"] and r["rank"] <= k)
        print(f"Recall@{k}: {hit}/{len(ans)} = {hit / len(ans):.1%}")
    for t in sorted({r["type"] for r in ans}):
        sub = [r for r in ans if r["type"] == t]
        hit = sum(1 for r in sub if r["rank"] and r["rank"] <= 5)
        print(f"  type {t}: Recall@5 {hit}/{len(sub)}")
    ms = sorted(r["ms"] for r in rows)
    print(f"search ms mean {statistics.mean(ms):.0f} p95 {ms[int(len(ms) * 0.95) - 1]}")
    print("misses @5:", [(r["id"], r["ranked"][:5]) for r in ans if not (r["rank"] and r["rank"] <= 5)])

if mode == "chat":
    # Warm-up, discarded.
    with post("/chat/stream", {"query": "Hello"}, token) as r:
        r.read()
    out = (HERE / f"chat_results{suffix}.jsonl").open("w")
    for q in questions:
        t, ttft, done, err = time.monotonic(), None, None, None
        try:
            with post("/chat/stream", {"query": q["q"]}, token) as r:
                for raw in r:
                    line = raw.decode().strip()
                    if not line.startswith("data: ") or line == "data: [DONE]":
                        continue
                    ev = json.loads(line[6:])
                    if ev["type"] == "text" and ttft is None:
                        ttft = time.monotonic() - t
                    elif ev["type"] == "done":
                        done = ev["response"]
                    elif ev["type"] == "error":
                        err = ev.get("message")
        except Exception as e:  # noqa: BLE001
            err = repr(e)
        total = time.monotonic() - t
        answer = (done or {}).get("answer", "")
        row = {
            "id": q["id"], "type": q["type"], "q": q["q"], "answer": answer,
            "refused": (done or {}).get("refused"), "error": err,
            "cited": [doc_id(c["title"]) for c in (done or {}).get("citations", [])],
            "keys_hit": keys_hit(answer, q["keys"]), "keys_total": len(q["keys"]),
            "ttft_s": round(ttft, 2) if ttft else None, "total_s": round(total, 2),
        }
        out.write(json.dumps(row) + "\n")
        out.flush()
        print(q["id"], row["keys_hit"], "/", row["keys_total"], "refused" if row["refused"] else "", err or "", flush=True)
