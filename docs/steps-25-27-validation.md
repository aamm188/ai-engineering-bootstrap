# Steps 25–27 Validation Record

## Implemented

- **25 — Failure → Recovery → Re-plan Integration**
  - Replanable execution failures trigger a fresh audit.
  - A new deterministic plan is generated and validated again.
  - Safety and human-approval boundaries are reapplied before re-execution.
  - Replanning is explicitly bounded by `max_replans` (default: 1).

- **26 — Execution Audit & Run Evidence**
  - Each pipeline run has a `run_id`.
  - Ordered immutable evidence events cover audit, planning, validation, approval,
    execution, verification, recovery, and terminal state.
  - Evidence is currently held in memory; no persistence dependency was introduced.

- **27 — Agent Runtime / Session Boundary**
  - Agent decision/planning runs inside `AgentRuntime` and an explicit session identity.
  - The Agent runtime exposes no execution, shell, or handler API.
  - Agent output remains downstream of Planner and cannot bypass safety or approval.

## Validation

- Pytest: **193 passed** in the current source snapshot.
- Feature tests: **37 passed** for approval, bootstrap workflow, and hardening paths.
- Compile check: **passed**.
- `git diff --check`: **passed**.
- Approval propagation: verified from Pipeline approval gate into REAL Executor.
- Duplicate handler action IDs: verified to accept independent approval IDs for
  separate package-install targets.
- Safe pipeline behavior: remains unchanged.

## Current correction

The dependency remediation workflow uses the shared handler action ID
`install_python_package` for multiple package targets. Approval state is therefore
carried as one or more approval IDs per action ID rather than overwriting a previous
approval. After the Pipeline approval gate succeeds, REAL execution receives the
approved state; this prevents the Executor from rejecting an action that has already
passed the Pipeline approval gate.

The current source snapshot has not been assigned a new commit hash by this review.

Cursor integration remains milestone **29** and was intentionally not mixed into
steps 25–27.
