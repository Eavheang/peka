# Search index measurements for issue #100

Run on 2026-11-07 against a throwaway `pgvector/pgvector:pg16` container (pgvector 0.8.6), not the live database. [`measure.py`](measure.py) reproduces the runs, and [`ann-output.txt`](ann-output.txt) holds the raw recall output and query plans. "Old" is the query from before migration 021, run in the same process on the same migrated data.

## Real data

A `pg_dump` copy of the local stack: 70 files, 506 chunks, 20 distinct documents. This is an older index than the 682 chunks in the final report.

| Measure | Old | New |
|---|---|---|
| `search_chunks` median, staff access | 108 ms | 22 ms |
| `search_chunks` median, full access | 102 ms | 27 ms |
| Document Recall@1 / 5 / 10 after reranking, 116 labelled questions | 113 / 116 / 116 | 113 / 116 / 116 |

Format copies tie, and index use changes which copy comes first, so the same section can come from a different format. The real model was not re-run, so answer quality was not measured.

## Larger corpus

The real data plus generated documents, 47,066 chunks in total. Each generated chunk joins 4 random sentences from the real chunks and 3 random words, embedded by the real model (`bge-small-en-v1.5`). Each document is stored as 3 format copies with identical vectors, half of them confidential.

| 58 labelled questions | Old | New |
|---|---|---|
| `search_chunks` median, staff access | 578 ms | 203 ms |
| `search_chunks` median, full access | 1,070 ms | 252 ms |
| Document Recall@1 / 5 / 10 after reranking | 32 / 54 / 58 | 30 / 50 / 57 |

The expected document was in the top 20 before reranking for all 58 questions, in all four new variants below. The loss comes from the reranker. Generated chunks repeat real sentences word for word under other names, and collapsing copies earlier puts more of those distractors in front of it. That makes this corpus harsher than a real one, but the trade-off is real.

| New query, Recall@1 / 5 / 10 | HNSW | Exact |
|---|---|---|
| Reads `top_k * 24` candidates | 30 / 50 / 57 | 30 / 50 / 57 |
| Reads `top_k * 4` candidates | 32 / 52 / 58 | 32 / 52 / 58 |

The index does not change these figures. The smaller candidate read lets copies crowd other documents out of the pool again, so `top_k * 24` stays.

## HNSW settings

Recall of the exact top 80 for a plain access-filtered vector query at staff access, on 55,034 chunks built the same way. Exact search took 190 ms. Counting by content treats a format copy as the same result.

| `m` / `ef_construction` | `ef_search` | Recall by ID | Lowest | Recall by content | Lowest | Time |
|---|---|---|---|---|---|---|
| 16 / 64 | 80 | 0.855 | 0.375 | 0.885 | 0.375 | 2.5 ms |
| 16 / 64 | 1000 | 0.968 | 0.863 | 0.991 | 0.833 | 7.3 ms |
| 32 / 200 | 80 | 0.934 | 0.637 | 0.951 | 0.613 | 2.8 ms |
| 32 / 200 | 1000 | 0.988 | 0.925 | 0.998 | 0.867 | 10.5 ms |

The last row is what ships. The index took 29.9 s to build on 47,066 chunks and uses 44 MB. An earlier run with Gaussian noise added to embeddings reached only about 0.6, and that was an artifact of the noise.

Top-20 overlap of the whole search query with the index against without it, over 43 questions: 0.988 for staff access (lowest 0.95), 0.992 for full access (lowest 0.95).

**Planner use:** on this corpus the planner used HNSW for full access. For staff access it preferred an exact parallel scan, which only costs time, since half the rows fail the filter and 480 candidates are requested. Most of the remaining time is the keyword branch, which ranks every matching chunk (29,456 of them in the sampled plan).

## Telling copies from unrelated files

Cosine similarity between file centroids on the real corpus:

| Pairs | Lowest | 5th percentile | Mean | 95th percentile | Highest |
|---|---|---|---|---|---|
| Same name (150) | 0.895 | 0.929 | 0.976 | 0.999 | 1.000 |
| Different name (2,265) | 0.577 | 0.676 | 0.781 | 0.845 | 0.967 |

The threshold of 0.85 kept every real copy pair collapsed. Unrelated files with the same name can still collapse if they are unusually similar, and no real pair of that kind was available to test.
