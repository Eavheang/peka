#!/usr/bin/env python3
"""Print top cosine scores for in-corpus vs out-of-corpus PEKA questions.

Uses the live embedding service and Postgres index (same path as chat retrieval),
but ignores SEARCH_SIMILARITY_FLOOR so weak hits still appear for calibration.

Pick NO_EVIDENCE_THRESHOLD at the value that best separates the two groups'
top scores (midpoint of the largest gap between sorted scores when the groups
do not overlap; otherwise the midpoint between group medians).

Usage (from service/ with .env loaded and embeddings + DB up):

    python scripts/calibrate_no_evidence_threshold.py
"""
from __future__ import annotations

import statistics
import sys
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR))

from app.config import settings
from app.engine.search.service import access_levels_for_role, embed_query
from app.engine.search.repository import search_repository

# Questions the PEKA knowledge base is expected to answer when those docs are indexed.
IN_CORPUS = [
    "What does the Q3 plan say about the launch date?",
    "What is our expense approval procedure?",
    "How many days of leave does every employee get?",
    "What is the attendance requirement in the school policy?",
    "What are the salary bands for senior engineers?",
    "Summarize the refund rules in the policy handbook.",
    "What disciplinary levels does the school policy define?",
]

# Questions PEKA documents cannot answer: off-topic and close-but-not-covered.
OUT_OF_CORPUS = [
    # Off-topic
    "Who won the 2018 FIFA World Cup?",
    "What is the capital of Mongolia?",
    "How do I bake sourdough bread at home?",
    "What is the current price of Bitcoin?",
    # Close but not covered (company-shaped, wrong facts / absent topics)
    "What is our pet-friendly office dog policy?",
    "What is the Q4 acquisition price for Acme Corp?",
    "How many remote-work stipends do contractors receive in Antarctica?",
    "What is the confidential bonus formula for interns in FY2012?",
]


def top_score(query: str, role: str = "admin") -> float | None:
    vector = embed_query(query)
    rows = search_repository.search_chunks(
        vector,
        access_levels_for_role(role),
        top_k=1,
        similarity_floor=0.0,
    )
    return float(rows[0]["score"]) if rows else None


def scores_for(questions: list[str]) -> list[float]:
    out: list[float] = []
    for question in questions:
        score = top_score(question)
        print(f"  {score if score is not None else 'none':>8}  {question}")
        if score is not None:
            out.append(score)
    return out


def summarize(name: str, scores: list[float]) -> None:
    if not scores:
        print(f"{name}: no scores (empty index or embed failure)")
        return
    print(
        f"{name}: n={len(scores)} min={min(scores):.4f} "
        f"median={statistics.median(scores):.4f} max={max(scores):.4f}"
    )


def choose_cutoff(in_scores: list[float], out_scores: list[float]) -> float | None:
    if not in_scores or not out_scores:
        return None
    # Largest gap on the sorted unique boundary between the groups.
    points = sorted({*in_scores, *out_scores})
    best_gap = -1.0
    best_mid: float | None = None
    for low, high in zip(points, points[1:]):
        mid = (low + high) / 2
        # Prefer cuts that put every out-of-corpus score below and every in-corpus above.
        if max(out_scores) < mid <= min(in_scores) and (high - low) > best_gap:
            best_gap = high - low
            best_mid = mid
    if best_mid is not None:
        return best_mid
    # Overlap: fall back to midpoint of medians (still report as a suggestion).
    return (statistics.median(in_scores) + statistics.median(out_scores)) / 2


def main() -> int:
    print(f"embedding_model={settings.embedding_model}")
    print(f"current NO_EVIDENCE_THRESHOLD={settings.no_evidence_threshold}")
    print()
    try:
        print("IN_CORPUS top scores")
        in_scores = scores_for(IN_CORPUS)
        print()
        print("OUT_OF_CORPUS top scores")
        out_scores = scores_for(OUT_OF_CORPUS)
    except RuntimeError as error:
        print(f"Calibration could not run: {error}")
        print("Leave NO_EVIDENCE_THRESHOLD marked uncalibrated.")
        return 2
    print()
    summarize("IN_CORPUS", in_scores)
    summarize("OUT_OF_CORPUS", out_scores)
    cutoff = choose_cutoff(in_scores, out_scores)
    if cutoff is None:
        print("Could not choose a cutoff (need scores in both groups).")
        return 1
    print(f"suggested NO_EVIDENCE_THRESHOLD={cutoff:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
