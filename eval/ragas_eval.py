"""Answer-quality check: ask PEKA the questions in questions.jsonl and score the replies.

Two passes, each resumable (finished rows are skipped on rerun, so a rate limit only pauses the run):
  1. ask   -> results/answers.jsonl  PEKA's answer, citations and the cited passage texts
  2. score -> results/scores.jsonl   retrieval hits + RAGAS faithfulness / context recall / context precision

Env: PEKA_URL, PEKA_EMAIL, PEKA_PASSWORD, JUDGE_BASE_URL, JUDGE_API_KEY, JUDGE_MODEL.
"""
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from statistics import mean

import httpx
from openai import AsyncOpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import ContextPrecision, ContextRecall, Faithfulness

HERE = Path(__file__).parent
RESULTS = HERE / os.environ.get("RESULTS_DIR", "results")
ANSWERS = RESULTS / "answers.jsonl"
SCORES = RESULTS / "scores.jsonl"
METRICS = ("doc_hit", "heading_hit", "faithfulness", "context_recall", "context_precision")


def load(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    if path.suffix == ".json":
        return {row["id"]: row for row in json.loads(path.read_text())}
    rows = (json.loads(line) for line in path.read_text().splitlines() if line.strip())
    return {row["id"]: row for row in rows}


def append(path: Path, row: dict) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def ask(questions: list[dict]) -> None:
    done = load(ANSWERS)
    peka = httpx.Client(base_url=os.environ.get("PEKA_URL", "http://localhost:8000"), timeout=300)
    login = {"email": os.environ["PEKA_EMAIL"], "password": os.environ["PEKA_PASSWORD"]}
    token = peka.post("/auth/login", json=login).raise_for_status().json()["access_token"]
    peka.headers["authorization"] = f"Bearer {token}"
    for q in questions:
        if q["id"] in done:
            continue
        reply = peka.post("/chat", json={"query": q["question"]})
        if reply.status_code != 200:
            print(f"ask {q['id']}: HTTP {reply.status_code} {reply.text[:200]} (rerun to retry)")
            continue
        reply = reply.json()
        passages = []
        for c in reply["citations"]:
            preview = peka.post("/chat/source-preview", json={k: c.get(k) for k in ("chunk_id", "title", "heading")})
            passages.append(preview.json()["content"] if preview.status_code == 200 else c.get("excerpt") or "")
        # Keep the user's chat history clean: the eval conversation is not real usage.
        if reply.get("conversation_id"):
            peka.delete(f"/chat/conversations/{reply['conversation_id']}")
        append(ANSWERS, {
            "id": q["id"], "answer": reply["answer"], "refused": reply["refused"],
            "citations": [{k: c.get(k) for k in ("title", "heading", "chunk_id")} for c in reply["citations"]],
            "passages": passages,
        })
        print(f"ask {q['id']}: {len(passages)} citations")


async def score(questions: list[dict]) -> None:
    answers, done = load(ANSWERS), load(SCORES)
    client = AsyncOpenAI(base_url=os.environ["JUDGE_BASE_URL"], api_key=os.environ["JUDGE_API_KEY"], max_retries=5)
    llm = llm_factory(os.environ["JUDGE_MODEL"], client=client)
    faithfulness, recall, precision = Faithfulness(llm=llm), ContextRecall(llm=llm), ContextPrecision(llm=llm)
    for q in questions:
        a = answers.get(q["id"])
        if a is None or q["id"] in done:
            continue
        if q.get("unanswerable"):
            # Nothing in the corpus answers it: citing nothing is the correct behaviour.
            append(SCORES, {"id": q["id"], "abstained": int(not a["citations"])})
            print(f"score {q['id']}: abstained={int(not a['citations'])}")
            continue
        stem = Path(q["file"]).stem.lower()
        row = {
            "id": q["id"],
            "doc_hit": int(any(stem in c["title"].lower() for c in a["citations"])),
            "heading_hit": int(any(stem in c["title"].lower() and c["heading"] == q["heading"] for c in a["citations"])),
        }
        # A citation shows title + heading + passage; chunk text alone often omits who it is about.
        contexts = [f"{c['title']} > {c['heading']}\n{p}" for c, p in zip(a["citations"], a["passages"]) if p.strip()]
        try:
            if contexts:
                row["faithfulness"] = (await faithfulness.ascore(
                    # "[1]" markers point at the UI's source list; the judge reads them as unsupported claims.
                    user_input=q["question"], response=re.sub(r"\s*\[\d+\]", "", a["answer"]),
                    retrieved_contexts=contexts)).value
                row["context_recall"] = (await recall.ascore(
                    user_input=q["question"], retrieved_contexts=contexts, reference=q["reference"])).value
                row["context_precision"] = (await precision.ascore(
                    user_input=q["question"], retrieved_contexts=contexts, reference=q["reference"])).value
            else:
                # No cited passage: nothing backs the answer and nothing relevant was found.
                row.update(faithfulness=0.0, context_recall=0.0, context_precision=0.0)
        except Exception as error:  # judge rate limit / bad JSON: leave the row unscored for the next run
            print(f"score {q['id']}: {type(error).__name__}: {str(error)[:200]} (rerun to retry)")
            continue
        append(SCORES, row)
        print(f"score {q['id']}: " + " ".join(f"{m}={row[m]:.2f}" for m in METRICS))


def report(questions: list[dict]) -> None:
    scores = load(SCORES)
    print(f"\nscored {len(scores)}/{len(questions)} questions")
    answerable = [r for r in scores.values() if "abstained" not in r]
    if answerable:
        for m in METRICS:
            print(f"{m:18} {mean(float(r[m]) for r in answerable):.3f}  (n={len(answerable)})")
    if unanswerable := [r["abstained"] for r in scores.values() if "abstained" in r]:
        print(f"{'abstained':18} {mean(unanswerable):.3f}  (n={len(unanswerable)}, unanswerable questions)")


if __name__ == "__main__":
    questions = list(load(HERE / os.environ.get("QUESTIONS", "questions.jsonl")).values())
    steps = sys.argv[1:] or ["ask", "score"]
    if "ask" in steps:
        ask(questions)
    if "score" in steps:
        asyncio.run(score(questions))
    report(questions)
