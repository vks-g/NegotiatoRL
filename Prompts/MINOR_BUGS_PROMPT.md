Fix the following two issues in the NegotiationRL project. Make minimal, surgical changes only.

---

## FIX 1: hard_hardliner max_rounds mismatch

**Problem:** `inference.py` has `max_rounds: 10` for the `hard_hardliner` task in `ALL_TASKS`, 
but `openenv.yaml` specifies `max_rounds: 15` (and `max_steps: 15`) for that task. 
Also, the step loop uses the global `MAX_STEPS = 10` constant instead of the task's own `max_rounds`.

**File:** `inference.py`

**Change 1:** In the `ALL_TASKS` list, update the `hard_hardliner` entry's `max_rounds` from `10` to `15`:
```python
{
    "name": "hard_hardliner",
    "strategy_name": "hardliner",
    "seed": 42,
    "max_rounds": 15,   # <-- change from 10 to 15
    "description": "Hard: Hardliner opponent who barely concedes",
},
```

**Change 2:** In the `run_task()` function, replace the hardcoded `MAX_STEPS` in the loop bound 
with the task config's own `max_rounds`:
```python
# BEFORE:
for step in range(1, MAX_STEPS + 1):

# AFTER:
for step in range(1, task_config["max_rounds"] + 1):
```

This ensures each task uses exactly the number of rounds defined in openenv.yaml, 
and a future change to any task's max_rounds only needs to be made in one place (ALL_TASKS).

---

## FIX 2: Replace placeholder HF username in README.md

**Problem:** `README.md` (at the repo root) contains 8 occurrences of the placeholder 
string `YOUR_HF_USERNAME` that were never replaced with the actual value.

**File:** `README.md`

**Change:** Do a global find-and-replace of every occurrence of `YOUR_HF_USERNAME` 
with `your-username` (or whatever the actual HF username is for this project). 
If the actual HF username is not known, use `your-username` as a safe neutral placeholder 
that at least makes it clear it is not a literal template token.

Verify with: `grep -c "YOUR_HF_USERNAME" README.md` — result should be `0` after the fix.

---

## Verification checklist after both fixes:

1. `grep "max_rounds" inference.py` → hard_hardliner entry shows `15`, not `10`
2. `grep "MAX_STEPS" inference.py` → should only appear in the constant definition line, 
   NOT in the `for step in range(...)` loop inside `run_task()`
3. `grep "YOUR_HF_USERNAME" README.md` → should return nothing (exit code 1)
4. `grep "max_rounds" negotiation_env/openenv.yaml` → confirm yaml still shows `15` for hard_hardliner (do not touch this file)

No other files need to be changed.
