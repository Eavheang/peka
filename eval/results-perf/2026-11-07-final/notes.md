# Final evaluation, 2026-11-07: notes on the raw output

Isolated Compose stack (own Postgres, embeddings, reranker and storage), attached to the project's llama container. Commit base `1603d8e` plus the changes for #96 and #101. Settings are in the [final report](../../../docs/final-report.md#test-system).

| File | Corpus | Made by |
|------|--------|---------|
| `answers.json` | 70 files | `perf_eval.py answers` |
| `recall-70files.json` | 70 files | `perf_eval.py recall` |
| `ramp-70files.json` | 70 files | `perf_eval.py ramp 1 2 3 4 6 10` |
| `recall-270files.json` | 270 files | `perf_eval.py recall question-scale.json questions.jsonl question-2.json` |
| `latency-270files.json` | 270 files | `perf_eval.py latency` |
| `ramp-270files.json` | 270 files | `perf_eval.py ramp 1 2 3 4 6 10` |
| `load-1user.json`, `load-2users.json`, `load-10users.json` | 270 files | `perf_eval.py load 1 3 4`, `load 2 3 4`, `load 10 2 8` |
| `evidence-scores-70files.txt`, `evidence-scores-270files.txt` | as named | One-off script: for each question, runs the access-filtered search and the reranker, and lists the top score. Each group shows its statistics and its lowest scores |

The run stopped by itself if the model fell below 40 tokens per second, checked before and after each step. It stayed at 85 to 87. Over the whole run the service logged 0 `Context size has been exceeded` errors and 0 reranker failures. No other client used the model: the project's own service logged no chat requests during the run.

`recall-70files.json` and `evidence-scores-70files.txt` came from an earlier pass on the same code and corpus, while the GPU was slow. They do not use the language model.

## Hand grades for `answers.json`

Answerable: 57 of 59 correct. Question 29 is partly correct: it gives the supply agreement's 12% limit and leaves out the 8% inspection limit. Question 31 is wrongly declined. Unanswerable (60 to 67): 8 of 8 declined. Question 66 was refused by the server, and the others were declined in words.

## Long conversations (#96)

Each user continues a conversation seeded with 20 messages of 1,200 characters, taken from the corpus chunks with the highest share of digits and table separators. Refusal was off (`SEARCH_EVIDENCE_FLOOR=0`) so that the question reached the model. 70 files.

The question: "Using every document you can find, write an extremely detailed and complete report of at least 3000 words covering the company's finances, policies, staffing and every metric, reproducing all the tables in full."

| Code | Users and rounds | Answered | Seconds per turn | `Context size` errors in the log |
|------|------------------|----------|------------------|-----------------------------------|
| Before | 2 users, 2 rounds | 0 of 4 | about 41 | 8 |
| After | 2 users, 4 rounds | 8 of 8 | 36 to 45 | 0 |
| After | 4 users, 1 round | 4 of 4 | 35 to 76 | 0 |

Before the change the failing slots stopped at 8,174 to 8,212 tokens, and the largest in those runs was 8,348. After it the largest was 5,727, and 6 replies reached the 2,048-token limit.

Other checks on the same setup, before and after:

- A short question on long histories: 15 of 15 before the change (11 on ordinary chunks, 4 on table-heavy ones), and 4 of 4 on table-heavy ones after it.
- A history whose newest assistant message is 20,000 characters, so the prompt starts with a cut assistant message: answered, and llama accepted the message order.
- Two users each sending a question of about 4,000 characters on a long history: both answered.

Measured token counts from llama's `/tokenize`, over all 682 chunks: system prompt 340 plus the date line, the 5 largest chunks 2,224 in total, metadata and wrapper for 5 sources 857, snippets for 5 sources about 535. The densest sampled chunk had 2.46 characters per token, and the median was 4.44.

## Refusal on the real model (#101)

One run per question through `POST /chat/stream`, in a new conversation, on 70 files.

Not refused, 13 of 13: hello; hi there; thanks!; good morning, how are you?; what is 2+2?; what is 17 * 23?; What is the capital of France?; Explain what a neural network is.; write a python function that reverses a string; who are you?; what can you do?; Who won the 2022 FIFA World Cup?; Who wrote Hamlet? The last two were declined in words ("The provided documents do not contain...").

Refused, 9 of 9, in 1.7 to 2.6 s: What is the CEO's home address?; What is the company's policy on bringing pets to the office?; What was the 2019 revenue of the Tokyo subsidiary?; What is the Wi-Fi password for the Phnom Penh office?; How many seats will the new cafe have?; Who owns the warehouse inventory optimization report's executive summary and what is its date?; Who owns the mobile app accessibility audit executive summary?; In the Food Safety SOP, what are the baseline and target for hand hygiene?; How much did we spend on the Jakarta office last year?

Broad requests, 9 of 10 answered: Summarize all the documents; Give me an overview of the company; What documents do you have?; What is in the knowledge base?; Tell me about Mekong Harvest Foods; What is this company about?; Summarize the employee handbook; What are the main risks?; What should I know before my first day? Refused: List the key numbers from the latest report.

An earlier version of the classifier refused 4 of these 10 and answered "other" questions with no sources. It was changed to refuse only specific facts and to leave every other turn unchanged.
