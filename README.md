# AI Engineering Bootstrap

AI Engineering Bootstrap is a deterministic, production-oriented platform for preparing,
validating, planning, and safely operating an AI engineering environment.

The project started as a Python CLI for environment auditing and project generation.
It is now evolving toward a controlled engineering workflow whose final primary user
interface will be a professional GUI.

## Product Goal

The target workflow is:

```text
Environment
    ↓
Probes
    ↓
Doctor / Audit
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

The important architectural principle is that diagnosis, planning, execution, and
presentation are separate responsibilities.

The CLI is primarily a developer, automation, CI/CD, and diagnostic interface.
CLI cosmetic polish is not the main product objective. The professional GUI is the
long-term primary user experience and must reuse the same application/core services.

## Current Implemented Baseline

The current `main` branch includes:

- read-only environment probes;
- Doctor / AuditService;
- unified Doctor audit models;
- development/production readiness;
- Health Score;
- check categorization;
- deterministic JSON/CI audit output;
- context-aware recommendations;
- Planner Foundation;
- deterministic `ExecutionPlan` generation;
- stable `ExecutionPlanAction` identifiers;
- priority ordering and duplicate-action elimination;
- safe handling of unknown audit checks;
- template discovery and safe project generation.

Recent accepted milestones:

```text
Doctor V2
Doctor V3 Model Unification
Doctor V3 Health Score
Doctor V3 Check Categorization
Doctor V3 CI/CD Audit Output
Doctor V3 Context-Aware Recommendations
Planner Foundation
```

## Current CLI

```text
ai-bootstrap audit [--format table|json]
ai-bootstrap doctor
ai-bootstrap plan
ai-bootstrap bootstrap
ai-bootstrap run-pipeline [--real-execution]
ai-bootstrap list-templates
ai-bootstrap create-project PROJECT_NAME --template TEMPLATE_NAME
```

`audit` is read-only and can produce deterministic JSON suitable for automation.

`doctor` presents categorized health information, readiness, health score, and
context-aware recommendations.

`plan` converts the current audit report into an `ExecutionPlan`.

`run-pipeline` runs the controlled backend workflow. Safe Mode remains non-mutating;
real execution is explicit and remains subject to validation, safety, approval,
execution, verification, and bounded recovery.

## Architecture

The canonical application pipeline is:

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
Validation / Safety / Approval
  ↓
Executor
  ↓
Verification
  ↓
Recovery / Re-plan
  ↓
CLI / GUI
```

- Probes observe the environment.
- Doctor diagnoses and reports.
- Planner plans remediation.
- Executor will be the only write-capable layer.
- CLI and GUI present and orchestrate through application services.

No presentation layer may bypass the pipeline or duplicate business logic.

## GUI Priority

The final product is intended to have a professional GUI.

The GUI should eventually expose:

- environment/health dashboard;
- categorized checks;
- recommendations;
- execution plan;
- user approval;
- execution progress;
- execution results and logs;
- post-execution verification.

The GUI must use the same core/application services as the CLI.

## Development Rules

Never commit directly to `main`.

Every feature is developed on a dedicated branch, tested, committed, pushed,
and then merged.

Minimum validation:

```bash
git diff --check
ruff check .
pytest
ai-bootstrap audit
ai-bootstrap doctor
ai-bootstrap plan
```

Run feature-specific smoke tests as required.

## Documentation Index

| Document | Purpose |
|---|---|
| `AGENTS.md` | Mandatory startup rules for coding AIs |
| `IMPLEMENTATION_WORKFLOW.md` | Feature implementation workflow |
| `docs/CONSTITUTION.md` | Frozen project rules |
| `docs/PROJECT_CONTEXT.md` | Current project state and continuation context |
| `docs/architecture.md` | Current architecture |
| `docs/roadmap.md` | Current roadmap and phases |
| `docs/development/git-workflow.md` | Branch/commit/merge workflow |
| `docs/development/bootstrap-process.md` | Target bootstrap workflow |
| `ADR/` | Accepted architectural decisions |

For a new AI, the repository state and Git history are authoritative for what is
already implemented. Do not treat old roadmap text as proof that a feature is still
pending.
