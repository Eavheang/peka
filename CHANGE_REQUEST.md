# Code Review — D-06 No Evidence Refusal

**Branch:** feat/d06-no-evidence-refusal  
**Commit:** 356daa8 Refuse chat turns when knowledge retrieval lacks evidence  
**Spec:** D-06 ticket requirements  
**Status:** CHANGES REQUIRED

---

## Critical Issues (Blockers)

### 1. ❌ Missing UI Refusal Card Implementation
**Spec requirement (Behavior #5):**
> "The UI shows a distinct refusal card when answer_status = 'refused': clear 'no evidence found in your documents' text, no citations, and a hint to upload documents or rephrase. Never an empty bubble."

**Current state:** Zero frontend changes in diff. The backend added `answer_status` field, but:
- `webclient/interface/chat.ts` does not include `answer_status` in `ChatResponse` or `ChatResult` types
- `webclient/app/(workspace)/workspace/_partials/chat.tsx` only shows basic "Not enough evidence" label, not a distinct refusal card
- No hint to upload documents or rephrase

**Action required:**
1. Update `ChatResponse` and `ChatResult` types to include `answer_status: 'answered' | 'refused'`
2. Create a distinct refusal card component when `answer_status === 'refused'`:
   - Display clear message: "No evidence found in your documents"
   - Hide citations (empty array, so this follows naturally)
   - Add hint: "Upload relevant documents or rephrase your question"
   - Style distinctly (consider a warning/empty state card)
3. Update `ChatMessageBubble` to render refusal card when `result.answer_status === 'refused'`

---

### 2. ⚠️ Audit Events for Refused Turns Not Visible
**Spec requirement (Behavior #4):**
> "The chat audit event is still written for refused turns."

**Current state:** The diff imports `record_audit_event`, but refusal paths return early without visible audit logging:
- `answer_from_knowledge()` returns `_no_evidence_response()` with no audit call
- `stream_answer_from_knowledge()` yields early without audit

**Verify/Action required:**
- Check if audit logging happens in the HTTP handler/route layer (outside `service.py`)
- If not, add explicit `record_audit_event()` calls in refusal paths in both sync and stream
- Or confirm in PR that audit logging is guaranteed by route-level middleware and add a note

---

### 3. ⚠️ Threshold Not Calibrated, No Sign-Off
**Spec requirement (Acceptance #6):**
> "Threshold calibrated on real data (or Eavheang accepts 0.70 as untuned)"

**Current state:** Default 0.70 is hardcoded as untuned; no evidence of calibration or Eavheang sign-off.

**Action required:**
- Either: run `scripts/calibrate_no_evidence_threshold.py` on real index, record results, and update `app/config.py` with tuned value
- Or: add explicit note in PR that Eavheang accepts 0.70 as untuned default, with plan to tune later

---

## Standards Issues (Judgement Calls)

### 4. Duplicated Code in Sync/Stream Paths
**Location:** `service/app/chat/service.py`, lines ~494–510 and ~530–540

The threshold check and results extraction repeat:
```python
retrieval = search_knowledge(search_plan.query, user_role)
if _lacks_evidence(retrieval.top_score):
    return/yield _no_evidence_response()
results = retrieval.hits
```

**Recommendation:** Extract a helper to reduce duplication, or accept as mild (the sync/async difference makes extraction awkward).

---

### 5. `answer_status` as Computed Alias
**Location:** `service/app/chat/schemas.py`, lines ~75–78

`answer_status` is purely `"refused" if self.refused else "answered"` — a computed alias of the existing `refused` boolean.

**Comment:** This duplication is justified only if the spec explicitly requires `answer_status` for the API contract (it does, for the frontend). But consider: does the internal service really need both `refused` and `answer_status`? If the spec only requires `answer_status` in the response, refactor to replace `refused` with `answer_status` everywhere (not both).

**For now:** Keep both since the spec names `answer_status` and existing code uses `refused`. Make a debt note if cleanup is wanted.

---

### 6. Two Cosine Thresholds, Unclear Difference
**Location:** `service/app/config.py`, lines ~22–25

```python
search_similarity_floor: float = 0.3       # filters hits in SQL
no_evidence_threshold: float = 0.70        # refuses on top score
```

**Issue:** The names do not explain why two cutoffs exist or how they differ. Code must read `repository.py` and `service.py` to learn that 0.30 drops hits from retrieval and 0.70 refuses after retrieval.

**Recommendation:** Add a docstring comment:
```python
# Cosine similarity cutoffs (bge-small embeddings):
#   search_similarity_floor: min score to include in retrieval result (SQL filter)
#   no_evidence_threshold: min top score to call LLM for KB turns (refusal)
# No_evidence_threshold > floor ensures refused turns are never empty hits.
```

---

### 7. Calibration Script Design Concerns
**Location:** `service/scripts/calibrate_no_evidence_threshold.py`

Minor issues:
- Imports `embed_query` directly, duplicating the embed + search logic from `search_knowledge()`
- Uses `sys.path.insert` as a workaround; other scripts may not follow this pattern
- `choose_cutoff()` logic is more complex than the "midpoint of gap" description suggests

**Recommendation:** Document assumptions (IN_CORPUS vs OUT_OF_CORPUS question lists should be representative), and note that the script is a one-off calibration tool, not production code.

---

### 8. `similarity_floor` Parameter Not Used in Production
**Location:** `service/app/engine/search/repository.py`, new `similarity_floor` param

Only the calibration script uses this parameter; production code always uses `settings.search_similarity_floor`.

**Recommendation:** Accept as justified (the script needs to bypass the floor to see all scores). Document in the script.

---

## Minor Notes

- **Web search path:** Correctly does not refuse (per spec). ✓
- **Test coverage:** All four threshold cases covered. ✓
- **Refused turn behavior:** No LLM call, no citations. ✓
- **Manual pre-ship verification:** Not shown in diff (Acceptance #7 requires one cited + one refusal on local run).

---

## Summary

| Category | Count | Severity |
|----------|-------|----------|
| Blockers | 3 | 🔴 CRITICAL |
| Judgement calls | 5 | 🟡 MINOR |
| **Status** | | **CHANGES REQUIRED** |

**Before merge, must resolve:**
1. Implement UI refusal card (frontend)
2. Verify/add audit logging for refused turns
3. Calibrate threshold or get sign-off on 0.70
4. Manual check: one cited answer + one refusal local run

**Post-merge or next iteration (non-blocking):**
1. Reduce duplication in sync/stream paths (mild)
2. Consider refactoring `refused` vs `answer_status` (defer)
3. Document threshold differences in config (quick win)
4. Clean up calibration script design (post-launch)
