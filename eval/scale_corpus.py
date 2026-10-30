"""Add or remove a synthetic corpus for the Recall@5 scale test. Runs inside the okf-worker container:

  docker exec -i config-okf-worker-1 python - add [count]    < eval/scale_corpus.py   # also writes /tmp/question-scale.json
  docker exec -i config-okf-worker-1 python - remove         < eval/scale_corpus.py

Documents go through the real chunker and embedding service, but skip the LLM conversion step: the OKF
page is written here, so indexing 200+ documents takes minutes instead of hours. Every row it adds has a
path starting with `others/scale-test-`; `remove` deletes exactly those (chunks and jobs cascade).
"""
import hashlib
import json
import random
import sys

from app.database import get_connection
from app.engine.chunks.chunker import parse_okf_chunks
from app.engine.chunks.embeddings import embed_chunks
from app.engine.chunks.repository import knowledge_chunks_repository

PREFIX = "others/scale-test-"
SYLLABLES = "bra cal dor el fen gar hel ion jur kel lom mar nev or pel qua rin sol tav ul ven wex yor zan".split()
NOUNS = "Harbour Valley Cold-Chain Packaging Logistics Billing Onboarding Procurement Warehouse Fleet Payroll Analytics Compliance Training Facilities".split()
KINDS = "Audit Pilot Policy Review Plan Procedure Report".split()
METRICS = "Rate Limits|Stock Accuracy|Response Time|Defect Rate|Training Hours|Budget Variance|Audit Findings|Uptime|Churn|Cycle Time|Safety Incidents|Renewal Rate".split("|")
OWNERS = "Amara Singh|Tomas Beck|Linh Tran|Priya Nair|Marcus Hale|Sofia Reyes|Kenji Mori|Ayesha Khan|Lars Holm|Nadia Petrova|Omar Said|Chloe Martin|Ravi Patel|Elena Rossi|Daniel Cho".split("|")
AREAS = "transport|cloud hosting|cleaning services|software licences|security staffing|equipment leasing|catering|printing".split("|")
MONTHS = "January February March April May June July August September October November December".split()
PURPOSE = [
    "The team documented how {a} and {b} interact across each phase of the plan. Stakeholders agreed that {a} has the largest effect on overall outcomes.",
    "Feedback gathered during the pilot showed that {a} needed simpler guidance. A clear owner for {b} reduces delays and keeps decisions traceable.",
    "Leaders should revisit {a} every quarter to confirm the assumptions still hold. Comparisons with peer organizations show similar patterns in {b}.",
]
RISKS = [
    "Without a baseline for {a}, it is difficult to judge whether progress is real. Open questions about {b} are listed in the appendix and assigned to named owners.",
    "The approach keeps {a} visible on the dashboard so that issues surface early. Any change to {b} should be tested before it reaches production.",
]


def build(count: int) -> list[dict]:
    rng = random.Random(7)
    names, docs = set(), []
    while len(docs) < count:
        coined = "".join(rng.choice(SYLLABLES) for _ in range(3)).capitalize()
        title = f"{coined} {rng.choice(NOUNS)} {rng.choice(KINDS)}"
        if title in names:
            continue
        names.add(title)
        i = len(docs) + 1
        metrics = [(m, rng.randint(20, 60), rng.randint(61, 99), rng.choice(OWNERS)) for m in rng.sample(METRICS, 4)]
        vendor = "".join(rng.choice(SYLLABLES) for _ in range(3)).capitalize() + " " + rng.choice(["Ltd", "Group", "Partners"])
        area, month, day, amount = rng.choice(AREAS), rng.choice(MONTHS), rng.randint(1, 28), rng.randint(12, 480) * 1000
        pick = lambda pool: rng.choice(pool).format(a=rng.choice(METRICS).lower(), b=rng.choice(METRICS).lower())
        table = "| Metric | Baseline | Target | Owner |\n|---|---|---|---|\n" + "\n".join(f"| {m} | {b}% | {t}% | {o} |" for m, b, t, o in metrics)
        slug = title.lower().replace(" ", "-")
        md = (
            f"---\ntitle: {title}\nsummary: A {title.split()[-1].lower()} covering {metrics[0][0].lower()} and {metrics[1][0].lower()}.\n---\n\n"
            f"# Purpose\n\n{pick(PURPOSE)}\n\n# Key Metrics\n\n{table}\n\n"
            f"# Decisions\n\nThe steering group selected {vendor} for {area} in {month}. The contract starts on {month} {day}. Approved budget: {amount} USD.\n\n"
            f"# Risks\n\n{pick(RISKS)}\n"
        )
        m, _, t, o = metrics[0]
        docs.append({
            "path": f"{PREFIX}{i:03d}-{slug}.md", "title": title, "markdown": md,
            "questions": [
                {"question": f"In the {title}, who owns {m} and what is its target?", "reference": f"{o}, target {t}%", "heading": "Key Metrics"},
                {"question": f"According to the {title}, which vendor was selected for {area} and when does the contract start?", "reference": f"{vendor}, starting {month} {day}", "heading": "Decisions"},
            ],
        })
    return docs


def add(count: int) -> None:
    docs, questions = build(count), []
    with get_connection() as connection:
        author = connection.execute("SELECT id FROM users WHERE role = 'admin' ORDER BY created_at LIMIT 1").fetchone()["id"]
    for doc in docs:
        sha = hashlib.sha256(doc["markdown"].encode()).hexdigest()
        with get_connection() as connection:
            file_id = connection.execute(
                "INSERT INTO files (path, content_type, author_id, sha256) VALUES (%s, 'text/markdown', %s, %s) RETURNING id",
                (doc["path"], author, sha),
            ).fetchone()["id"]
            connection.execute("INSERT INTO okf_jobs (file_id, status) VALUES (%s, 'completed')", (file_id,))
        chunks = parse_okf_chunks({"files": [{"file_type": "okf_concept", "content": doc["markdown"]}], "document_analysis": {"title": doc["title"]}})
        knowledge_chunks_repository.swap_active_set(file_id, chunks, embed_chunks(chunks))
        questions += [{"id": len(questions) + 1, "file": doc["path"].rsplit("/", 1)[-1], **q} for q in doc["questions"]]
    with open("/tmp/question-scale.json", "w") as f:
        json.dump(questions, f, indent=1)
    print(f"added {len(docs)} documents, {len(questions)} questions")


def remove() -> None:
    with get_connection() as connection:
        n = connection.execute("DELETE FROM files WHERE path LIKE %s", (PREFIX + "%",)).rowcount
    print(f"removed {n} files")


if sys.argv[1] == "add":
    add(int(sys.argv[2]) if len(sys.argv) > 2 else 200)
else:
    remove()
