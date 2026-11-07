# Search index measurements for issue #100

Run on 2026-11-07 against a throwaway `pgvector/pgvector:pg16` container (pgvector 0.8.6), not the live database. "Old" is the query from `origin/main`, run in the same process against the same migrated data.

## Real data

A `pg_dump` copy of the local stack: 70 files, 506 chunks, 20 distinct documents. This is an older index than the 682 chunks in the final report.

| Measure | Old | New |
|---|---|---|
| `search_chunks`, median | 109 ms | 22 ms |
| Document Recall@1 / 5 / 10 after reranking, 116 labelled questions | 113 / 116 / 116 | 113 / 116 / 116 |

With index scans and bitmap scans disabled, the new query returned the same IDs in the same order as the old one in all 282 runs (141 questions at two access levels). With the GIN index on, the top-5 file set differed for 45 of 141 questions. The sampled worst case had the same document and sections from another format copy. Those copies tie, and index use changes which one comes first. The real model was not re-run, so answer quality was not measured.

## Synthetic scale

The real data plus 500 generated files (half confidential) of 100 chunks each, 50,506 chunks in total. Each generated chunk copies a random real chunk, adds a unique token and adds Gaussian noise (sigma 0.035) to its embedding, then normalizes it. This produces many near-duplicates, as format copies do, so it is a hard case for an approximate index, and recall is counted by chunk ID.

| Median over 30 questions | Old | New, GIN only |
|---|---|---|
| Staff access | 1,678 ms | 554 ms |
| Full access | 3,282 ms | 762 ms |

## Why there is no HNSW index

The planner used an HNSW index scan for the vector branch with the access filter applied, with `hnsw.iterative_scan = strict_order`. Accuracy was the problem. Recall of the exact top 80, for staff access over 30 questions:

| `hnsw.ef_search` | Mean recall | Lowest | Query time |
|---|---|---|---|
| 80 | 0.589 | 0.0 | 2.3 ms |
| 200 | 0.627 | 0.0 | 2.1 ms |
| 400 | 0.662 | 0.0 | 3.0 ms |
| 1000 | 0.675 | 0.0 | 4.6 ms |

Exact vector search on the same data took 153 ms (staff) and 194 ms (full access). `m` and `ef_construction` were left at their defaults and not tuned. Generated data may overstate the loss, so measure on a real corpus before reconsidering.
