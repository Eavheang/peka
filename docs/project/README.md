# Project record

The academic record of PEKA (Private Enterprise Knowledge Assistant), a Batch 11 final-year software project at Kirirom Institute of Technology, run from 13 July to 7 November 2026. These pages hold the requirements, design, testing and evaluation evidence in one place, checked against the code on `main`. The rest of `docs/` explains how the system works and how to run it.

| Page | Contents | Thesis section |
|------|----------|----------------|
| [Objectives and evaluation](objectives-and-evaluation.md) | Problem, aim, the five objectives with verdicts, offline and deployment tests | Problem Statement, Chapter 1, 4.6 |
| [Related work](related-work.md) | Existing systems, techniques, tool choices, comparison and gap, references | Chapter 2 |
| [Requirements](requirements.md) | Stakeholders, roles, functional and non-functional requirements with final status, user stories | 3.1 |
| [Methodology and timeline](methodology-and-timeline.md) | Process, timeline, reviews, quality controls, risks, data and ethics | 3.2 |
| [Design](design.md) | Components, use cases, ER diagram, sequences, decision flow, deployment, API groups | 3.3 to 3.5 |
| [Scope changes](scope-changes.md) | Proposal versus final system, with reasons | Chapters 1, 3 and 5 |
| [Testing](testing.md) | Strategy, test inventory, test cases, traceability, defects | 4.4, Appendix C |
| [Final report](../final-report.md) | Recall, answer quality, latency, load and refusal measurements | 4.5, 4.7 |

Other pages the thesis draws on:

| Thesis section | Source |
|----------------|--------|
| 3.4 Workflows and algorithms | [How it works](../how-it-works.md), [Key flows](../architecture/flows.md), [Indexing](../architecture/indexing.md), [Chat and RAG](../architecture/chat-and-rag.md) |
| 3.5 Interface and security | [User guide](../user-guide.md), [Web client](../webclient/README.md), [Security](../security.md) |
| 4.1 Environment | [System requirements](../system-requirements.md), [Getting started](../getting-started.md), [Config](../config/README.md) |
| 4.2 Modules | [Service](../service/README.md), [API reference](../service/api-reference.md), [Data model](../service/data-model.md) |
| Appendix A, user manual | [User guide](../user-guide.md) |
| Appendix B, technical manual | [System requirements](../system-requirements.md), [Getting started](../getting-started.md), [Backup and restore](../backup-and-restore.md), [Glossary and troubleshooting](../glossary-and-troubleshooting.md) |
| Raw evaluation data | [`eval/`](../../eval/README.md) |

Unless a page says otherwise, facts refer to `main` at commit `4a08cd9` (12 November 2026).
