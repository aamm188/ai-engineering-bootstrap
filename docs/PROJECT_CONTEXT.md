# Project Context — Master Development Reference

## Project Identity

**Repository:** `aamm188/ai-engineering-bootstrap`

GitHub is the source of truth.

The reference development runtime is Ubuntu 24.04 LTS.

## Product Goal

Build a production-grade AI Engineering Bootstrap platform that can:

1. inspect an engineering environment;
2. diagnose its state;
3. calculate readiness and health;
4. generate a deterministic remediation plan;
5. let the user review/approve that plan;
6. execute approved changes safely;
7. verify the resulting environment;
8. provide the complete workflow through a professional GUI.

Target workflow:

```text
Environment
   ↓
Inspect / Probes
   ↓
Doctor
   ↓
AuditReport
   ↓
Planner
   ↓
ExecutionPlan
   ↓
User Review / Approval
   ↓
Executor
   ↓
Verification
   ↓
Doctor again
```

## Current Implementation Status

### Completed

- Bootstrap foundation
- Environment probes
- AuditService / Doctor
- unified Doctor audit models
- development readiness
- production readiness
- Health Score
- check categorization
- deterministic audit JSON / CI output
- context-aware recommendations
- Planner Foundation
- `ExecutionPlan`
- `ExecutionPlanAction`
- stable action IDs
- priority ordering
- duplicate-action elimination
- safe handling of unknown failed checks
- template discovery and safe project generation

### Current Baseline

`main` is the stable integration branch.

Planner Foundation has been merged into `main`.

### Next

```text
Executor Foundation
```

## Architecture

```text
Probe
  ↓
Doctor / AuditService
  ↓
AuditReport
  ↓
Planner
  ↓
ExecutionPlan
  ↓
Executor
  ↓
Application Workflow
  ↓
CLI / Professional GUI
```

### Responsibilities

**Probe**

Read-only environment observation.

**Doctor**

Single source of diagnostics. Produces readiness, Health Score, categories,
recommendations, and `AuditReport`.

**Planner**

Consumes `AuditReport` and produces deterministic `ExecutionPlan`.

**Executor**

Only write-capable layer. Consumes `ExecutionPlan`.

**Application Workflow**

Coordinates Doctor → Planner → Executor and verification.

**CLI**

Developer, diagnostic, automation, and CI/CD interface.

**GUI**

Long-term primary product interface. Must use the same core/application services.

## Frozen Rules

- Never duplicate business logic.
- Never duplicate Doctor models.
- Doctor is the source of truth for diagnostics.
- Planner consumes Doctor public models.
- Executor consumes Planner public models.
- Probe/Doctor/Planner are read-only.
- Executor alone can modify the environment.
- CLI/GUI cannot bypass the pipeline.
- Backward compatibility is mandatory.
- No unnecessary runtime dependencies.
- No speculative abstractions.
- No unrelated refactors during feature implementation.
- Every feature is tested.
- Never commit directly to `main`.

## Development Workflow

Every feature:

```text
updated main
    ↓
feature branch
    ↓
read project rules + inspect current code
    ↓
implement smallest coherent change
    ↓
tests
    ↓
ruff
    ↓
git diff --check
    ↓
CLI smoke tests
    ↓
commit
    ↓
push
    ↓
merge
    ↓
verify main
```

## Mandatory AI Startup

A coding AI must read:

```text
AGENTS.md
docs/CONSTITUTION.md
relevant ADRs
IMPLEMENTATION_WORKFLOW.md
docs/PROJECT_CONTEXT.md
docs/architecture.md
relevant source/tests
```

Then inspect:

```bash
git status
git log --oneline --decorate -5
```

The current repository and Git history override stale roadmap statements.

## Next Feature — Executor Foundation

The immediate feature is:

```text
feature/executor-foundation
```

The goal is to establish the execution contract and safety boundary, not to build a
large remediation framework.

Expected scope:

- Executor public protocol/contract;
- execution result model(s);
- consume `ExecutionPlan`;
- explicit action execution boundary;
- deterministic behavior;
- safe/dry-run semantics where required;
- unit/integration tests;
- integration path for the future application workflow.

Do not add:

- autonomous agent behavior;
- LLM integration;
- broad remediation catalog;
- GUI business logic;
- unrelated refactors.

## Product Priority

Priority order:

```text
1. Correct core architecture
2. Doctor → Planner → Executor workflow
3. Safety and deterministic execution
4. Application workflow
5. Professional GUI
6. CLI cosmetic improvements
```

The CLI must remain stable and automation-friendly, but professional GUI capability
is a major product objective.

## Current Foundation Status — Steps 19–27

The following milestones are implemented on the current baseline:

19. **LLM Provider Integration** — local HTTP, remote API-key, in-process Python,
    plus deterministic Mock provider and provider factory.
20. **Agent Decision → Planner Integration** — structured Agent decisions can be
    deterministically converted into `ExecutionPlan` objects without an execution
    path from Agent to Executor.
21. **Capability → Action Contract Binding** — capability metadata is validated
    against registered handlers and explicit policies.
22. **Environment Dependency Discovery & Remediation Planning** — Python dependencies
    are discovered from `pyproject.toml`; missing dependencies become typed
    remediation actions.
23. **Controlled Real Action Pack — Phase 1** — controlled real handlers exist for
    virtual-environment creation and Python/project dependency installation. Safe
    mode remains non-mutating.
24. **Dependency Installation Workflow** — the complete path from Doctor through
    planning, validation, safety, approval, real execution, and independent
    verification is available as a backend workflow.
25. **Failure → Recovery → Re-plan Integration** — replanable failures trigger a fresh
    audit and deterministic plan rebuild with a bounded replan count; the safety and
    approval boundaries are reapplied before the new plan can execute.
26. **Execution Audit & Run Evidence** — each pipeline run emits immutable, ordered
    evidence events with run identity, timestamps, stage status, and recovery details.
27. **Agent Runtime / Session Boundary** — Agent decision/planning is isolated inside
    a bounded session object with explicit lifecycle identity and no execution API.

The next planned milestone is **28. End-to-End Autonomous Environment Bootstrap**.
Cursor installation/engineering-environment bootstrap remains a later milestone and
must not be mixed into dependency remediation for project runtime dependencies.
