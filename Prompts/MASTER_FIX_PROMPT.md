# MASTER FIX PROMPT — NegotiationRL Hackathon Submission
## For: Claude Opus / Senior Coding Agent
## Priority: All fixes are BLOCKING submission. Do every single one.

---

## YOUR MISSION

You are fixing a Python RL environment project called **NegotiationRL** for a hackathon
submission. There are **4 critical bugs** and **1 important improvement** that must be fixed
before the submission can pass automated validation. This document tells you exactly what
is broken, exactly why, exactly what to change, and exactly what the fixed version must
look like. Do not improvise. Follow the instructions precisely.

The project structure at the repo root looks like this:

```
NegotiatoRL-main/
├── inference.py                              ← FIX REQUIRED (Bug 2 + Bug 4)
├── README.md
├── Information/                              ← DO NOT TOUCH
├── .dockerignore
└── negotiation_env/                          ← outer folder, NOT a Python package
    ├── openenv.yaml                          ← FIX REQUIRED (Bug 3)
    ├── pyproject.toml
    ├── uv.lock
    ├── README.md
    └── negotiation_env/                      ← INNER folder, THIS is the Python package
        ├── __init__.py
        ├── models.py
        ├── client.py
        ├── rewards.py
        ├── strategies.py
        ├── cli.py
        ├── test_env.py
        └── server/
            ├── __init__.py
            ├── app.py                        ← FIX REQUIRED (Bug 1 partial)
            ├── environment.py
            └── Dockerfile                    ← FIX REQUIRED (Bug 1 main)
```

---

## BUG 1 — CRITICAL: Dockerfile PYTHONPATH and CMD are wrong (container crashes on start)

### File to edit: `negotiation_env/negotiation_env/server/Dockerfile`

### WHY THIS IS BROKEN

The Dockerfile copies the outer `negotiation_env/` folder into `/app/negotiation_env/`
inside the container. After this COPY, the filesystem inside the container looks like:

```
/app/
└── negotiation_env/              ← outer folder (no __init__.py here)
    ├── openenv.yaml
    ├── pyproject.toml
    └── negotiation_env/          ← ACTUAL Python package (has __init__.py)
        ├── __init__.py
        ├── models.py
        └── server/
            └── app.py
```

The current ENV line sets:
```
PYTHONPATH="/app:$PYTHONPATH"
```

And the current CMD runs:
```
uvicorn negotiation_env.server.app:app
```

Python with `PYTHONPATH=/app` looks for `/app/negotiation_env/__init__.py` to find the
`negotiation_env` package. But `/app/negotiation_env/__init__.py` does NOT EXIST — the
real `__init__.py` is at `/app/negotiation_env/negotiation_env/__init__.py`. So uvicorn
crashes immediately with `ModuleNotFoundError: No module named 'negotiation_env.server'`
and the container exits. The HF Space shows as unhealthy. This is an automatic disqualification.

### THE FIX

Change `PYTHONPATH` so it points to `/app/negotiation_env` (the outer folder). Then Python
will find `negotiation_env/__init__.py` relative to that, i.e., the inner package, and
`import negotiation_env` will work correctly. The CMD stays the same.

### EXACT CHANGE — find this block in the Dockerfile:

```dockerfile
# Set environment variables
ENV PYTHONPATH="/app:$PYTHONPATH" \
    PYTHONUNBUFFERED=1 \
    HOST="0.0.0.0" \
    PORT="8000" \
    WORKERS="1"
```

### REPLACE IT WITH:

```dockerfile
# Set environment variables
# IMPORTANT: PYTHONPATH must point to the outer negotiation_env/ folder so that
# Python can find the inner negotiation_env/ package (which has __init__.py).
# Container layout after COPY: /app/negotiation_env/negotiation_env/__init__.py
# So PYTHONPATH=/app/negotiation_env makes `import negotiation_env` resolve correctly.
ENV PYTHONPATH="/app/negotiation_env:$PYTHONPATH" \
    PYTHONUNBUFFERED=1 \
    HOST="0.0.0.0" \
    PORT="8000" \
    WORKERS="1"
```

### ALSO FIX the build-stage COPY lines near the top of the Dockerfile

Currently there are two lines in the builder stage that reference wrong paths:
```dockerfile
COPY negotiation_env/pyproject.toml /app/negotiation_env/
COPY negotiation_env/__init__.py /app/negotiation_env/
```

The `__init__.py` is in the INNER package. These lines are also wrong but since they are
only for caching pip installs, the crash happens at CMD. Fix them anyway for correctness:

```dockerfile
COPY negotiation_env/pyproject.toml /app/negotiation_env/
COPY negotiation_env/negotiation_env/__init__.py /app/negotiation_env/negotiation_env/__init__.py
```

Wait — actually in the builder stage you only need pyproject.toml to install deps.
The `__init__.py` copy is unnecessary there. **Simplest fix for builder stage:**

```dockerfile
# Install Python dependencies
# Copy only pyproject.toml for dependency caching
COPY negotiation_env/pyproject.toml /app/pyproject.toml

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    "openenv-core>=0.1.0" \
    "pydantic>=2.0.0" \
    "fastapi>=0.100.0" \
    "uvicorn[standard]>=0.23.0" \
    "websockets>=11.0"
```

### ALSO UPDATE the Dockerfile comment header at the top:

Find this comment:
```dockerfile
# IMPORTANT: Build from repository root (required for Hugging Face Spaces)
#   docker build -t negotiation-env:latest -f negotiation_env/server/Dockerfile .
```

Replace with:
```dockerfile
# IMPORTANT: Build from repository root (required for Hugging Face Spaces)
#   docker build -t negotiation-env:latest -f negotiation_env/negotiation_env/server/Dockerfile .
#
# The Dockerfile path is: negotiation_env/negotiation_env/server/Dockerfile
# (note the double negotiation_env/ — outer folder contains the Python package)
```

### VERIFY the fix is correct by mentally tracing:
1. Build command: `docker build -f negotiation_env/negotiation_env/server/Dockerfile .`
2. `COPY negotiation_env /app/negotiation_env` copies the outer folder
3. Result: `/app/negotiation_env/negotiation_env/__init__.py` exists
4. `PYTHONPATH=/app/negotiation_env`
5. Python looks for `negotiation_env` package in `/app/negotiation_env/`
6. Finds `/app/negotiation_env/negotiation_env/__init__.py` ✅
7. CMD: `uvicorn negotiation_env.server.app:app` resolves to
   `/app/negotiation_env/negotiation_env/server/app.py` ✅

---

## BUG 2 — CRITICAL: inference.py cannot import negotiation_env (ImportError at startup)

### File to edit: `inference.py` (at the repo root)

### WHY THIS IS BROKEN

`inference.py` is at the repo root. It contains:
```python
from negotiation_env import NegotiationEnv, NegotiationAction
```

When Python runs `inference.py`, `sys.path` includes the repo root
(`NegotiatoRL-main/`). Python finds a **folder** called `negotiation_env` there.
But that folder is the OUTER folder — it has no `__init__.py`. So Python cannot
import from it and raises:

```
ImportError: cannot import name 'NegotiationEnv' from 'negotiation_env'
```

or:

```
ModuleNotFoundError: No module named 'negotiation_env'
```

The hackathon evaluator runs `python inference.py` from the repo root. It will
crash on line 1 before doing anything. This is an automatic disqualification
because "Baseline reproduces" requires the inference script to complete without error.

### THE FIX

Add a `sys.path` manipulation at the very top of `inference.py`, BEFORE any imports
from `negotiation_env`. This inserts the OUTER `negotiation_env/` folder onto `sys.path`,
so Python can then find the INNER `negotiation_env/` package inside it.

### EXACT CHANGE — find the import block at the top of inference.py:

```python
import asyncio
import os
import textwrap
from typing import Dict, List, Optional, Any

from openai import OpenAI

from negotiation_env import NegotiationEnv, NegotiationAction
```

### REPLACE IT WITH:

```python
import asyncio
import os
import sys
import textwrap
from typing import Dict, List, Optional, Any

# ---------------------------------------------------------------------------
# PATH FIX: Add the outer negotiation_env/ directory to sys.path so that the
# inner negotiation_env Python package (negotiation_env/negotiation_env/) is
# importable as `import negotiation_env`.
#
# Directory structure:
#   repo_root/                          ← inference.py lives here
#   repo_root/negotiation_env/          ← outer folder (no __init__.py)
#   repo_root/negotiation_env/negotiation_env/   ← Python package (__init__.py here)
#
# By inserting repo_root/negotiation_env into sys.path[0], Python resolves
# `import negotiation_env` to repo_root/negotiation_env/negotiation_env/.
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
_PKG_DIR = os.path.join(_REPO_ROOT, "negotiation_env")
if _PKG_DIR not in sys.path:
    sys.path.insert(0, _PKG_DIR)

from openai import OpenAI

from negotiation_env import NegotiationEnv, NegotiationAction
```

### NOTHING ELSE IN inference.py CHANGES for this fix.

---

## BUG 3 — CRITICAL: app.py uses `create_app` which may not exist in openenv-core

### File to edit: `negotiation_env/negotiation_env/server/app.py`

### WHY THIS IS BROKEN

The current code is:
```python
from openenv.core.env_server import create_app
```

All official OpenEnv documentation (README4.md in your Information/ folder) shows:
```python
from openenv.core.env_server import create_fastapi_app
```

If `openenv-core` does not export `create_app` (which is a non-standard name not in
the spec), the server will fail to import and crash immediately with:
```
ImportError: cannot import name 'create_app' from 'openenv.core.env_server'
```

This prevents the server from starting, making `/reset` return a connection error
instead of HTTP 200, failing the automated HF Space ping check.

### THE FIX

Use a safe import with fallback that tries both names, so the code works whether
`openenv-core` exports `create_fastapi_app`, `create_app`, or both:

### EXACT CHANGE — replace the entire content of `app.py` with:

```python
"""
FastAPI application for the Negotiation Environment server.

This module creates the FastAPI app using OpenEnv's app factory,
which automatically generates all required endpoints:
- /ws   - WebSocket endpoint for real-time communication
- /reset - HTTP endpoint to start a new episode
- /step  - HTTP endpoint to take an action
- /state - HTTP endpoint to get current state
- /health - Health check endpoint
- /docs  - OpenAPI documentation

Note: We pass the class (not instance) to the factory. This allows:
- HTTP endpoints: Uses a singleton/shared environment instance
- WebSocket: Creates a new instance per connection for session isolation
"""

# Import the app factory — try the documented name first, fall back to alias.
# openenv-core may export either 'create_fastapi_app' (spec name) or 'create_app' (alias).
try:
    from openenv.core.env_server import create_fastapi_app as _create_app
except ImportError:
    try:
        from openenv.core.env_server import create_app as _create_app  # type: ignore[no-redef]
    except ImportError as e:
        raise ImportError(
            "Could not import app factory from openenv.core.env_server. "
            "Tried: create_fastapi_app, create_app. "
            f"Original error: {e}"
        ) from e

from .environment import NegotiationEnvironment
from ..models import NegotiationAction, NegotiationObservation

# Create the FastAPI application.
# Passing the class (not an instance) allows the framework to manage
# lifecycle: singleton for HTTP, per-connection instance for WebSocket.
app = _create_app(
    NegotiationEnvironment,
    NegotiationAction,
    NegotiationObservation,
)
```

---

## BUG 4 — IMPORTANT: inference.py runs ALL 3 tasks in one execution (wrong pattern)

### File to edit: `inference.py` (at the repo root)

### WHY THIS IS A PROBLEM

The hackathon evaluator calls `inference.py` once **per task**, passing the task name
via an environment variable. The standard pattern (shown in Information/sample_inference.py)
is: read task name from env var → run exactly one episode → emit one [START]...[END] block.

Your current `main()` runs ALL 3 tasks in a loop, emitting 3 separate [START]/[END] blocks.
This means:
1. The evaluator may only read the first [END] line and ignore the rest, giving you 1/3 score.
2. The total runtime is 3x longer, potentially hitting the 20-minute limit.
3. The pattern deviates from the spec, which says "One [START] line at episode begin" —
   implying one episode per run.

### THE FIX

Add a `TASK_NAME` env var that controls which single task runs. If not set, default to
running all tasks (for local testing). The evaluator will set it to one of:
`easy_conceder`, `medium_tft`, `hard_hardliner`.

### EXACT CHANGE — find the TASKS list and everything below it until `async def main()`:

FIND this section (after the imports and config variables):

```python
# Task configurations matching openenv.yaml
TASKS = [
    {
        "name": "easy_conceder",
        "strategy_name": "conceder",
        "seed": 42,
        "max_rounds": 10,
        "description": "Easy: Conceder opponent who readily accepts reasonable offers",
    },
    {
        "name": "medium_tft",
        "strategy_name": "tit_for_tat",
        "seed": 42,
        "max_rounds": 10,
        "description": "Medium: Tit-for-Tat opponent who mirrors your concession rate",
    },
    {
        "name": "hard_hardliner",
        "strategy_name": "hardliner",
        "seed": 42,
        "max_rounds": 10,
        "description": "Hard: Hardliner opponent who barely concedes",
    },
]
```

REPLACE WITH:

```python
# ---------------------------------------------------------------------------
# Task configurations — must match tasks defined in openenv.yaml
# ---------------------------------------------------------------------------

# All available tasks (used when running locally without NEGOTIATION_TASK set)
ALL_TASKS = [
    {
        "name": "easy_conceder",
        "strategy_name": "conceder",
        "seed": 42,
        "max_rounds": 10,
        "description": "Easy: Conceder opponent who readily accepts reasonable offers",
    },
    {
        "name": "medium_tft",
        "strategy_name": "tit_for_tat",
        "seed": 42,
        "max_rounds": 10,
        "description": "Medium: Tit-for-Tat opponent who mirrors your concession rate",
    },
    {
        "name": "hard_hardliner",
        "strategy_name": "hardliner",
        "seed": 42,
        "max_rounds": 10,
        "description": "Hard: Hardliner opponent who barely concedes",
    },
]

# Map task names to their config for fast lookup
TASK_MAP = {t["name"]: t for t in ALL_TASKS}

# The hackathon evaluator sets NEGOTIATION_TASK to run a specific task.
# If not set, run all tasks (useful for local testing).
TASK_NAME_ENV = os.getenv("NEGOTIATION_TASK") or os.getenv("MY_ENV_V4_TASK")

# Resolve which tasks to run in this execution
if TASK_NAME_ENV:
    if TASK_NAME_ENV not in TASK_MAP:
        print(
            f"[DEBUG] Unknown task '{TASK_NAME_ENV}'. "
            f"Available: {list(TASK_MAP.keys())}. Defaulting to easy_conceder.",
            flush=True,
        )
        TASKS = [TASK_MAP["easy_conceder"]]
    else:
        # Single task mode — exactly what the evaluator expects
        TASKS = [TASK_MAP[TASK_NAME_ENV]]
else:
    # No task specified — run all (local testing mode)
    TASKS = ALL_TASKS
```

### ALSO UPDATE `async def main()` to handle both single-task and multi-task modes cleanly:

FIND:

```python
async def main() -> None:
    """Run all tasks and report scores."""
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    total_score = 0.0

    for task_config in TASKS:
        print(f"\n{'=' * 60}", flush=True)
        print(f"Running task: {task_config['name']}", flush=True)
        print(f"Description: {task_config['description']}", flush=True)
        print(f"{'=' * 60}\n", flush=True)

        score = await run_task(client, task_config)
        total_score += score

        print(
            f"\nTask {task_config['name']} completed with score: {score:.2f}\n",
            flush=True,
        )

    average_score = total_score / len(TASKS) if TASKS else 0.0
    print(f"\n{'=' * 60}", flush=True)
    print(f"FINAL RESULTS", flush=True)
    print(f"{'=' * 60}", flush=True)
    print(f"Total tasks: {len(TASKS)}", flush=True)
    print(f"Total score: {total_score:.2f}", flush=True)
    print(f"Average score: {average_score:.2f}", flush=True)
```

REPLACE WITH:

```python
async def main() -> None:
    """
    Run task(s) and report scores.

    In single-task mode (NEGOTIATION_TASK env var set): runs exactly one task,
    emitting one [START]...[END] block. This is the evaluator's expected pattern.

    In multi-task mode (no env var): runs all 3 tasks sequentially for local testing.
    """
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    total_score = 0.0
    single_task_mode = TASK_NAME_ENV is not None

    for task_config in TASKS:
        if not single_task_mode:
            # Only print separators in multi-task (local testing) mode
            print(f"\n{'=' * 60}", flush=True)
            print(f"Running task: {task_config['name']}", flush=True)
            print(f"Description: {task_config['description']}", flush=True)
            print(f"{'=' * 60}\n", flush=True)

        score = await run_task(client, task_config)
        total_score += score

        if not single_task_mode:
            print(
                f"\nTask {task_config['name']} completed with score: {score:.2f}\n",
                flush=True,
            )

    if not single_task_mode:
        # Summary only shown in multi-task local testing mode
        average_score = total_score / len(TASKS) if TASKS else 0.0
        print(f"\n{'=' * 60}", flush=True)
        print(f"FINAL RESULTS", flush=True)
        print(f"{'=' * 60}", flush=True)
        print(f"Total tasks: {len(TASKS)}", flush=True)
        print(f"Total score: {total_score:.2f}", flush=True)
        print(f"Average score: {average_score:.2f}", flush=True)
```

---

## BUG 5 — IMPORTANT: openenv.yaml grader block needs a callable fn reference

### File to edit: `negotiation_env/openenv.yaml`

### WHY THIS MAY BE A PROBLEM

The OpenEnv spec may require the `grader` field to include a `fn` key pointing to a
Python callable that can be called to score an episode. Your current grader blocks look like:

```yaml
grader:
  score_range: [0.0, 1.0]
  success_threshold: 0.5
  deterministic: true
```

This describes the grader but doesn't tell OpenEnv HOW to call it. If `openenv validate`
expects a `fn` field to verify the grader is callable, it will fail validation. The grader
function must accept the episode state and return a float in [0.0, 1.0].

Your environment already computes this via `GraderOutput` in the state. We need a
standalone grader function that `openenv validate` can call.

### THE FIX

#### Step 1: Create a new file `negotiation_env/negotiation_env/graders.py`

Create this file with the following content:

```python
"""
Grader functions for NegotiationEnv tasks.

Each grader takes the episode final state (as a dict from /state endpoint)
and returns a normalized score in [0.0, 1.0].

These are referenced in openenv.yaml under tasks[].grader.fn
"""

from typing import Any, Dict, Optional


def _extract_grader_output(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract grader output dict from state, handling both nested and flat formats."""
    # State may come as a dict from JSON deserialization
    grader = state.get("grader")
    if grader is None:
        return None
    if isinstance(grader, dict):
        return grader
    # If it's already a GraderOutput object (direct env usage)
    try:
        return grader.model_dump()
    except AttributeError:
        return dict(grader)


def grade_easy_conceder(state: Dict[str, Any]) -> float:
    """
    Grader for easy_conceder task.

    Scores based on:
    - Whether a deal was reached (primary signal)
    - Agent's utility relative to BATNA (secondary)

    Returns float in [0.0, 1.0].
    """
    grader = _extract_grader_output(state)

    if grader is None:
        # No grader output means episode ended abnormally
        return 0.0

    deal_reached = grader.get("deal_reached", False)

    if not deal_reached:
        return 0.0

    # Agent utility scaled to [0.5, 1.0] for deals above BATNA
    agent_utility = grader.get("agent_utility", 0.0)

    # Easy task: reward any deal, scale by utility quality
    score = min(1.0, 0.4 + 0.6 * agent_utility)
    return max(0.0, float(score))


def grade_medium_tft(state: Dict[str, Any]) -> float:
    """
    Grader for medium_tft task.

    Scores based on:
    - Deal reached (primary)
    - Joint surplus (efficiency of the deal)
    - Agent utility (quality for agent)

    Returns float in [0.0, 1.0].
    """
    grader = _extract_grader_output(state)

    if grader is None:
        return 0.0

    deal_reached = grader.get("deal_reached", False)

    if not deal_reached:
        return 0.0

    agent_utility = grader.get("agent_utility", 0.0)
    pareto_efficiency = grader.get("pareto_efficiency", 0.0)

    # Medium task: reward deals that are both good for agent AND efficient
    score = 0.5 * agent_utility + 0.5 * pareto_efficiency
    return max(0.0, min(1.0, float(score)))


def grade_hard_hardliner(state: Dict[str, Any]) -> float:
    """
    Grader for hard_hardliner task.

    Scores based on:
    - Deal reached (necessary for any positive score)
    - Agent utility (highly weighted — hardliner rarely gives good deals)
    - Negotiation efficiency (rewarding faster deals)

    Returns float in [0.0, 1.0].
    """
    grader = _extract_grader_output(state)

    if grader is None:
        return 0.0

    deal_reached = grader.get("deal_reached", False)

    if not deal_reached:
        # Hard task: partial credit for getting close (high concession from counterpart)
        total_counterpart_concession = grader.get("total_counterpart_concession", 0.0)
        # If counterpart conceded a lot but still no deal, give tiny credit
        return min(0.15, float(total_counterpart_concession) * 0.3)

    agent_utility = grader.get("agent_utility", 0.0)
    negotiation_efficiency = grader.get("negotiation_efficiency", 1.0)

    # Hard task: high weight on agent utility, bonus for fast resolution
    # negotiation_efficiency = rounds_used/rounds_available (lower = faster)
    speed_bonus = max(0.0, 1.0 - negotiation_efficiency) * 0.1
    score = 0.9 * agent_utility + speed_bonus
    return max(0.0, min(1.0, float(score)))
```

#### Step 2: Update `negotiation_env/openenv.yaml` — add `fn` to each grader block

FIND the tasks section and REPLACE the entire `tasks:` block with:

```yaml
# Task definitions (3 tasks with graders, easy → medium → hard)
tasks:
  - name: easy_conceder
    description: |
      Negotiate against a Conceder opponent who rapidly moves toward the midpoint
      and accepts offers at or above their BATNA. Tests basic negotiation skills
      and ability to recognize good deals.
    difficulty: easy
    max_steps: 10
    grader:
      fn: negotiation_env.graders:grade_easy_conceder
      score_range: [0.0, 1.0]
      success_threshold: 0.5
      deterministic: true
    reset_params:
      strategy_name: conceder
      max_rounds: 10
      seed: 42

  - name: medium_tft
    description: |
      Negotiate against a Tit-for-Tat opponent who mirrors your concession rate.
      Tests strategic reciprocity - agent must learn to make measured concessions
      to induce cooperation from the counterpart.
    difficulty: medium
    max_steps: 10
    grader:
      fn: negotiation_env.graders:grade_medium_tft
      score_range: [0.0, 1.0]
      success_threshold: 0.5
      deterministic: true
    reset_params:
      strategy_name: tit_for_tat
      max_rounds: 10
      seed: 42

  - name: hard_hardliner
    description: |
      Negotiate against a Hardliner opponent who barely concedes and demands
      near-aspiration utility. Tests patience, persistence, and ability to
      extract concessions from stubborn opponents under time pressure.
    difficulty: hard
    max_steps: 15
    grader:
      fn: negotiation_env.graders:grade_hard_hardliner
      score_range: [0.0, 1.0]
      success_threshold: 0.4
      deterministic: true
    reset_params:
      strategy_name: hardliner
      max_rounds: 15
      seed: 42
```

Note: `hard_hardliner` now uses `max_rounds: 15` (changed from 10). With only 10 rounds,
hardliner concedes only 20% total from aspiration — almost never enough to reach a deal.
15 rounds gives the agent a realistic chance.

#### Step 3: Add graders to `__init__.py` exports

In `negotiation_env/negotiation_env/__init__.py`, add the grader imports at the bottom:

FIND:

```python
__version__ = "1.0.0"
```

REPLACE WITH:

```python
__version__ = "1.0.0"

# Grader functions (imported for openenv.yaml fn references)
from .graders import grade_easy_conceder, grade_medium_tft, grade_hard_hardliner

__all__ += [
    "grade_easy_conceder",
    "grade_medium_tft",
    "grade_hard_hardliner",
]
```

---

## FINAL VERIFICATION CHECKLIST

After making all changes, verify each fix mentally:

### Fix 1 (Dockerfile):
- [ ] `ENV PYTHONPATH="/app/negotiation_env:$PYTHONPATH"` (not `/app`)
- [ ] `CMD uvicorn negotiation_env.server.app:app ...` unchanged
- [ ] Builder stage COPY for `__init__.py` fixed or removed
- [ ] Header comment updated with correct Dockerfile path

### Fix 2 (inference.py):
- [ ] `import sys` added to stdlib imports
- [ ] `_REPO_ROOT` and `_PKG_DIR` defined before any negotiation_env import
- [ ] `sys.path.insert(0, _PKG_DIR)` called before `from negotiation_env import ...`
- [ ] The `from negotiation_env import NegotiationEnv, NegotiationAction` line is KEPT, just moved to after the path fix

### Fix 3 (app.py):
- [ ] Try/except block wraps the import
- [ ] Tries `create_fastapi_app` first, falls back to `create_app`
- [ ] `_create_app(...)` called with same 3 arguments as before
- [ ] Relative imports `.environment` and `..models` unchanged

### Fix 4 (inference.py):
- [ ] `TASK_NAME_ENV = os.getenv("NEGOTIATION_TASK") or os.getenv("MY_ENV_V4_TASK")`
- [ ] `ALL_TASKS` list has all 3 tasks
- [ ] `TASK_MAP` dict created for fast lookup
- [ ] `TASKS` resolves to either 1 task (evaluator mode) or all 3 (local mode)
- [ ] `main()` updated to not print separators in single-task mode

### Fix 5 (openenv.yaml + graders.py):
- [ ] New file `negotiation_env/negotiation_env/graders.py` created
- [ ] All 3 grader functions implemented: `grade_easy_conceder`, `grade_medium_tft`, `grade_hard_hardliner`
- [ ] Each grader takes `Dict[str, Any]` and returns `float` in [0.0, 1.0]
- [ ] `openenv.yaml` tasks each have `fn: negotiation_env.graders:grade_<name>`
- [ ] `hard_hardliner` task now has `max_rounds: 15`
- [ ] `__init__.py` exports the 3 grader functions

---

## DO NOT TOUCH THESE FILES

Do not modify any of the following — they are correct as-is:
- `negotiation_env/negotiation_env/models.py`
- `negotiation_env/negotiation_env/rewards.py`
- `negotiation_env/negotiation_env/strategies.py`
- `negotiation_env/negotiation_env/client.py`
- `negotiation_env/negotiation_env/server/environment.py`
- `negotiation_env/negotiation_env/test_env.py`
- `negotiation_env/negotiation_env/cli.py`
- `negotiation_env/pyproject.toml`
- `README.md`
- `.dockerignore`
- Anything inside `Information/`
- Anything inside `.ai-workflow/`

---

## SUMMARY OF ALL FILES TO CREATE OR MODIFY

| Action | File |
|--------|------|
| MODIFY | `negotiation_env/negotiation_env/server/Dockerfile` |
| MODIFY | `inference.py` |
| MODIFY | `negotiation_env/negotiation_env/server/app.py` |
| MODIFY | `negotiation_env/openenv.yaml` |
| CREATE | `negotiation_env/negotiation_env/graders.py` |
| MODIFY | `negotiation_env/negotiation_env/__init__.py` |

That is 5 files modified and 1 file created. Total scope is small and targeted.
Every change is described exactly above with the FIND block and REPLACE block shown.
