"""Retrieval and performance checks against a running PEKA stack. Stdlib only.

  recall   Recall@5 / @10 of POST /search over the question files (no LLM involved)
  latency  time to first token and total time of POST /chat/stream, one user at a time
  load     N concurrent chat users, without and then with documents being indexed
  answers  each question on its own, keeping the reply, for grading by hand

Env: PEKA_URL (default http://localhost:8000), PEKA_EMAIL, PEKA_PASSWORD, RESULTS_DIR (default results-perf).
Output: <RESULTS_DIR>/<step>.json
"""
import json
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from statistics import mean, median

HERE = Path(__file__).parent
OUT = HERE / os.environ.get("RESULTS_DIR", "results-perf")
URL = os.environ.get("PEKA_URL", "http://localhost:8000")


def call(method, path, body=None, token=None, headers=None, raw=None, timeout=600):
    data = raw if raw is not None else json.dumps(body).encode() if body is not None else None
    h = {"content-type": "application/json", **(headers or {})}
    if token:
        h["authorization"] = f"Bearer {token}"
    req = urllib.request.Request(URL + path, data, h, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        text = r.read()
        return json.loads(text) if text else None


def login():
    return call("POST", "/auth/login", {"email": os.environ["PEKA_EMAIL"], "password": os.environ["PEKA_PASSWORD"]})["access_token"]


def questions(name):
    p = HERE / name
    if p.suffix == ".json":
        return json.loads(p.read_text())
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def pct(values, p):
    s = sorted(values)
    return s[min(len(s) - 1, round(p / 100 * (len(s) - 1)))] if s else None


def stats(values):
    return {"n": len(values), "mean": mean(values), "p50": median(values), "p95": pct(values, 95), "max": max(values)} if values else {"n": 0}


def stream_chat(token, query):
    """One streamed turn. Returns timings in seconds from sending the request."""
    t0 = time.monotonic()
    row = {"ok": False, "status": None, "ttft": None, "total": None, "error": None}
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request(URL + "/chat/stream", body, {"content-type": "application/json", "authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            for line in r:
                line = line.decode().strip()
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                ev = json.loads(line[6:])
                now = time.monotonic() - t0
                if ev["type"] == "status" and row["status"] is None:
                    row["status"] = now
                elif ev["type"] == "text" and row["ttft"] is None:
                    row["ttft"] = now
                elif ev["type"] == "error":
                    row["error"] = ev.get("message")
                elif ev["type"] == "done":
                    row["ok"] = True
                    row["citations"] = len(ev["response"].get("citations", []))
                    row["cited"] = sorted({c["title"] for c in ev["response"].get("citations", [])})
                    row["answer"] = ev["response"]["answer"]
                    row["refused"] = ev["response"]["refused"]
                    try:
                        call("DELETE", f"/chat/conversations/{ev['response']['conversation_id']}", token=token)
                    except Exception:
                        pass
    except Exception as e:
        row["error"] = f"{type(e).__name__}: {e}"
    row["total"] = time.monotonic() - t0
    return row


def summarize_turns(rows):
    good = [r for r in rows if r["ok"]]
    return {
        "requests": len(rows), "ok": len(good), "errors": [r["error"] for r in rows if not r["ok"]],
        "first_status_s": stats([r["status"] for r in good if r["status"] is not None]),
        "ttft_s": stats([r["ttft"] for r in good if r["ttft"] is not None]),
        "total_s": stats([r["total"] for r in good]),
    }


def recall(*names):
    token = login()
    indexed = {Path(f["path"]).stem.lower() for f in call("GET", "/files", token=token)}
    report = {"indexed_files": len(call("GET", "/files", token=token)), "indexed_stems": len(indexed)}
    for name in names or ("questions.jsonl", "question-2.json"):
        rows, stale = [], []
        for q in (q for q in questions(name) if not q.get("unanswerable")):
            files = q["file"] if isinstance(q["file"], list) else [q["file"]]
            stems = [Path(f).stem.lower() for f in files]
            if not any(s in indexed for s in stems):
                stale.append(q["id"])  # expected file is not in the knowledge base: not a retrieval miss
                continue
            t0 = time.monotonic()
            res = call("POST", "/search", {"query": q["question"]}, token)
            ms = (time.monotonic() - t0) * 1000
            doc_rank = next((i + 1 for i, r in enumerate(res) if any(s in r["title"].lower() for s in stems)), None)
            head_rank = next((i + 1 for i, r in enumerate(res) if any(s in r["title"].lower() for s in stems) and r["heading"] == q.get("heading")), None) if "heading" in q else None
            rows.append({"id": q["id"], "results": len(res), "doc_rank": doc_rank, "heading_rank": head_rank, "ms": ms})
        n = len(rows)
        hit = lambda key, k: sum(1 for r in rows if r[key] and r[key] <= k) / n
        report[name] = {
            "questions": n, "skipped_file_not_indexed": stale,
            "doc_recall@1": hit("doc_rank", 1), "doc_recall@5": hit("doc_rank", 5), "doc_recall@10": hit("doc_rank", 10),
            "search_ms": stats([r["ms"] for r in rows]),
            "misses@5": [r["id"] for r in rows if not (r["doc_rank"] and r["doc_rank"] <= 5)],
        }
        if any(r["heading_rank"] for r in rows):
            report[name].update({"heading_recall@5": hit("heading_rank", 5), "heading_recall@10": hit("heading_rank", 10)})
    save("recall-scale" if names else "recall", report)


def latency(n=20):
    token = login()
    qs = [q for q in questions("question-2.json") if not q.get("unanswerable")]
    random.Random(1).shuffle(qs)
    stream_chat(token, "warm up: what does Mekong Harvest Foods do?")  # first request loads caches
    rows = [stream_chat(token, q["question"]) for q in qs[:n]]
    save("latency", {"questions": [q["id"] for q in qs[:n]], "summary": summarize_turns(rows), "rows": rows})


def answers(name="question-2.json"):
    token = login()
    stream_chat(token, "warm up: what does Mekong Harvest Foods do?")
    rows = [{**q, **stream_chat(token, q["question"])} for q in questions(name)]
    save("answers", {"summary": summarize_turns(rows), "rows": rows})


def fake_doc(i):
    topic = f"Perf-Test-{uuid.uuid4().hex[:8]}"
    paras = [f"## Section {j}\n" + " ".join(f"The {topic} programme {i} uses control {j}-{k} with owner team {random.randint(1, 99)} and target {random.randint(10, 99)} percent." for k in range(12)) for j in range(6)]
    return f"perf-{topic}.md", f"# {topic} Plan\n\n" + "\n\n".join(paras)


def upload(token, name, text):
    b = uuid.uuid4().hex
    body = f'--{b}\r\nContent-Disposition: form-data; name="files"; filename="{name}"\r\nContent-Type: text/markdown\r\n\r\n{text}\r\n--{b}--\r\n'.encode()
    return call("POST", "/files", token=token, raw=body, headers={"content-type": f"multipart/form-data; boundary={b}"})[0]["id"]


def run_users(users, turns, qs):
    """`users` threads, each with its own login, asking `turns` questions back to back."""
    rows, lock = [], threading.Lock()

    def worker(u):
        token = login()
        for t in range(turns):
            r = stream_chat(token, qs[(u * turns + t) % len(qs)]["question"])
            with lock:
                rows.append(r)

    t0 = time.monotonic()
    threads = [threading.Thread(target=worker, args=(u,)) for u in range(users)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return rows, time.monotonic() - t0


def load(users=10, turns=2, docs=8):
    token = login()
    qs = [q for q in questions("question-2.json") if not q.get("unanswerable")]
    random.Random(2).shuffle(qs)
    stream_chat(token, "warm up: what does Mekong Harvest Foods do?")
    report = {"users": users, "turns_per_user": turns}

    rows, wall = run_users(users, turns, qs)
    report["without_indexing"] = {**summarize_turns(rows), "wall_s": wall}
    print("without indexing:", json.dumps(report["without_indexing"]["ttft_s"]), flush=True)

    ids = [upload(token, *fake_doc(i)) for i in range(docs)]
    t_up = time.monotonic()
    done_at, stop = {}, threading.Event()

    def watch():
        while not stop.is_set() or len(done_at) < len(ids):
            for fid in ids:
                if fid not in done_at and call("GET", f"/files/{fid}/okf-status", token=token)["okf_status"] in ("completed", "failed"):
                    done_at[fid] = time.monotonic() - t_up
            if stop.is_set() and time.monotonic() - t_up > 3600:
                break
            time.sleep(2)

    w = threading.Thread(target=watch)
    w.start()
    rows, wall = run_users(users, turns, qs)
    chat_done = time.monotonic() - t_up
    stop.set()
    w.join()
    status = [call("GET", f"/files/{fid}/okf-status", token=token)["okf_status"] for fid in ids]
    report["with_indexing"] = {
        **summarize_turns(rows), "wall_s": wall, "uploaded_docs": docs, "okf_status": status,
        "chat_finished_after_s": chat_done, "indexing_finished_after_s": max(done_at.values()) if done_at else None,
        "indexing_still_running_when_chat_ended": sum(1 for v in done_at.values() if v > chat_done),
    }
    for fid in ids:
        call("DELETE", f"/files/{fid}", token=token)
    save("load", report)


def ramp(*levels):
    """Concurrent users 1..N, one turn each, no indexing: where do errors start?"""
    token = login()
    qs = [q for q in questions("question-2.json") if not q.get("unanswerable")]
    random.Random(3).shuffle(qs)
    stream_chat(token, "warm up: what does Mekong Harvest Foods do?")
    save("ramp", {u: summarize_turns(run_users(u, 1, qs[u:] + qs[:u])[0]) for u in (levels or (1, 2, 3, 4, 6, 10))})


def save(name, report):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report["summary"] if "summary" in report else report, indent=2))


if __name__ == "__main__":
    step, args = sys.argv[1], [int(a) if a.isdigit() else a for a in sys.argv[2:]]
    {"recall": recall, "latency": latency, "load": load, "ramp": ramp, "answers": answers}[step](*args)
