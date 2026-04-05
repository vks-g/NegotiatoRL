# NegotiationRL v4 — Fix Prompt

Read this file carefully and apply ALL fixes in order. Each fix is precise and surgical.
Do not modify anything not explicitly listed here.

---

## FIX 1 — CRITICAL: score format in log_end() (inference.py)

**File:** `inference.py`

**Problem:** `log_end()` prints `score={score:.2f}` but the hackathon sample_inference.py
uses `score={score:.3f}`. The automated evaluator parses this field — wrong format = incorrect scoring.

**Find this line inside `log_end()`:**

```python
f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}",
```

**Replace with:**

```python
f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}",
```

Only change `.2f` to `.3f` on the `score=` field. The `rewards_str` stays `.2f`. Nothing else changes.

---

## FIX 2 — Remove dead code: MAX_STEPS constant (inference.py)

**File:** `inference.py`

**Problem:** `MAX_STEPS = 10` is defined at the top of the file but never used anywhere —
the loop now correctly uses `task_config["max_rounds"]`. Dead code is misleading.

**Find this line:**

```python
MAX_STEPS = 10
```

**Replace with:**

```python
# MAX_STEPS removed — loop uses task_config["max_rounds"] per task (see ALL_TASKS)
```

---

## FIX 3 — Grader partial-credit unreachable path (graders.py)

**File:** `negotiation_env/negotiation_env/graders.py`

**Problem:** In `grade_hard_hardliner`, the no-deal branch tries to read
`total_counterpart_concession` from the grader output, but when no deal is reached,
`state["grader"]` is `None` — so `_extract_grader_output` returns `None` and the
function already returns `0.0` before ever reaching that logic. The partial-credit
line is dead code.

**Find this block inside `grade_hard_hardliner`:**

```python
    if not deal_reached:
        # Hard task: partial credit for getting close (high concession from counterpart)
        total_counterpart_concession = grader.get("total_counterpart_concession", 0.0)
        # If counterpart conceded a lot but still no deal, give tiny credit
        return min(0.15, float(total_counterpart_concession) * 0.3)
```

**Replace with:**

```python
    if not deal_reached:
        # Hard task: small flat partial credit for attempting (grader may be None on no-deal)
        return 0.05
```

This makes the no-deal branch reachable and deterministic regardless of grader state.

---

## FIX 4 — Replace your-username placeholders in README.md

**File:** `README.md` (repo root)

**Problem:** 8 occurrences of `your-username` remain as unfilled placeholders.
These are visible to Phase 3 human reviewers.

**Action:** Do a global find-and-replace across the entire file.

Replace every occurrence of:

```
your-username
```

With your actual Hugging Face username. If the actual HF username is not yet known,
use `negotiatorl` as a neutral placeholder (it is at minimum not a template token).

**Verify after fix:**

```bash
grep -c "your-username" README.md
# Must return 0
```

---

## FIX 5 — Align Dockerfile WORKERS default with openenv.yaml

**File:** `negotiation_env/negotiation_env/server/Dockerfile`

**Problem:** `openenv.yaml` declares `workers: 4` but the Dockerfile sets `WORKERS="1"`.
The evaluator runs Docker directly so it gets 1 worker, not 4.

**Find this line in the ENV block:**

```dockerfile
    WORKERS="1"
```

**Replace with:**

```dockerfile
    WORKERS="4"
```

---

## Verification checklist — run after all fixes

```bash
# Fix 1: score field uses 3 decimal places
grep "score:.3f" inference.py
# Expected: 1 match inside log_end()

# Fix 2: MAX_STEPS constant is gone
grep "^MAX_STEPS" inference.py
# Expected: 0 matches (only the comment remains)

# Fix 3: no-deal path returns flat value
grep "return 0.05" negotiation_env/negotiation_env/graders.py
# Expected: 1 match inside grade_hard_hardliner

# Fix 4: no placeholder username
grep -c "your-username" README.md
# Expected: 0

# Fix 5: Dockerfile uses 4 workers
grep 'WORKERS="4"' negotiation_env/negotiation_env/server/Dockerfile
# Expected: 1 match
```

No other files should be modified.
