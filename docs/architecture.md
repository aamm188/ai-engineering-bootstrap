# Architecture

## 1. Scope

The project is a layered, deterministic AI Engineering Bootstrap platform.

The current implementation has evolved beyond the original Phase 1 audit/generation
CLI. The active core pipeline is:

```text
Probes
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
Application / CLI / GUI
```

The final product is intended to provide a professional GUI, while the CLI remains
important for development, diagnostics, automation, and CI/CD.

## 2. Dependency Direction

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
Application/UI
```

Presentation must not bypass these layers.

Forbidden:

```text
CLI → Probe
GUI → Probe
Planner → Probe
Executor → Probe
GUI → shell/remediation logic
CLI → remediation business logic
```

## 3. Probes

Probes are read-only environment observers.

They inspect facts such as:

- Python version;
- virtual environment;
- editable installation;
- required Python packages;
- Git;
- Docker;
- operating system;
- platform architecture;
- runtime target;
- best-effort GPU information.

A probe returns a typed result. It does not render output and does not perform
remediation.

## 4. Doctor / AuditService

Doctor is the single source of environment diagnostics.

Responsibilities:

- execute probes;
- normalize probe results;
- create `AuditCheck` objects;
- assign check categories;
- calculate readiness;
- calculate Health Score;
- produce deterministic `AuditReport` data;
- attach context-aware recommendations.

Doctor remains read-only.

Doctor must not execute remediation actions.

## 5. Audit Models

Doctor-specific models live in:

```text
src/ai_engineering_bootstrap/audit/models.py
```

This is the source of truth for:

- `AuditCheck`;
- `AuditReport`;
- `AuditStatus`;
- `CheckStatus`;
- `CheckCategory`;
- `EnvironmentReadiness`.

There must not be competing definitions of Doctor's `AuditCheck` or `AuditReport`.

Generic application models may remain in the root `models.py` only when they are
not Doctor-specific.

## 6. Planner

Planner consumes the public `AuditReport`.

Current Planner Foundation contains:

```text
src/ai_engineering_bootstrap/planner/models.py
src/ai_engineering_bootstrap/planner/engine.py
```

Public concepts:

- `ExecutionPlan`;
- `ExecutionPlanAction`.

Planner currently:

- maps known failed checks to stable action IDs;
- creates deterministic actions;
- assigns priorities;
- removes duplicate actions;
- safely ignores unknown failures;
- produces a summary;
- remains read-only.

Planner must consume public audit models and must not inspect probes.

## 7. Executor Boundary

Executor is the only layer allowed to modify the host environment.

The Executor Foundation is the next architectural milestone.

It must consume `ExecutionPlan` and execute only explicitly approved actions.

Executor must not become a second diagnostic system.

The intended boundary is:

```text
READ-ONLY
Probe
Doctor
Planner
        │
        ▼
WRITE
Executor
```

No remediation should be added to Doctor, Planner, CLI, or GUI.

## 8. Recovery, Evidence, and Agent Runtime

### Recovery boundary

Recovery is part of the application orchestration layer. A replanable failure
causes a fresh Doctor audit and deterministic Planner run. The candidate plan is
validated again and the same approval/safety boundary is applied before execution.
Replanning is explicitly bounded; it is not an open-ended Agent loop.

### Run evidence

Each pipeline run records immutable, ordered evidence events for audit, planning,
validation, approval, execution, verification, and recovery. The current implementation
keeps evidence in memory; durable storage is a later concern and is not required by
this milestone.

### Agent session boundary

The Agent runtime owns only a bounded decision/planning session. It may call the
configured provider and Planner bridge, but it has no execution method, shell access,
or direct handler access. Execution remains downstream of validation, approval,
SafetyGate, Executor, and Verification.

## 9. Application / Presentation

CLI and GUI are application/presentation entry points.

They may:

- invoke application services;
- display public models;
- collect user input/approval;
- report expected failures.

They must not contain independent business rules.

The future GUI is the primary product interface. CLI presentation should remain
stable, deterministic, scriptable, and useful without becoming a second product.

## 10. Determinism

For identical inputs/environment state, the system should produce stable:

- check ordering;
- categories;
- readiness;
- Health Score;
- recommendations;
- action IDs;
- action ordering;
- JSON structure.

Determinism is required for testing, CI/CD, debugging, and future GUI behavior.

## 11. Read/Write Safety

Audit and planning commands are read-only.

The controlled `run-pipeline` application flow may invoke the Executor, but only
after validation, SafetyGate, and any required human approval. Safe Mode remains
non-mutating.

Only the Executor performs approved environment changes.

## 12. Existing Generation Boundary

Project generation remains a separate application capability.

It validates project/template input, prevents destination collisions, and performs
controlled file generation according to the accepted generation ADR.

It must not be mixed with Doctor/Planner business logic.

## 13. Architecture Change Rule

Accepted interfaces, model contracts, dependency direction, collision semantics,
or read/write boundaries must not be changed casually.

Use a new or superseding ADR for architectural changes.

Do not redesign unrelated subsystems while implementing a feature.

## 14. Agent and Capability Boundary

The Agent/LLM layer is decision-only. It consumes context and capability metadata and
returns a structured `AgentDecision`. It must not contain executor handlers,
subprocess access, shell execution, or filesystem remediation logic.

```text
Context + Capability Metadata
            ↓
        Agent / LLM
            ↓
       AgentDecision
            ↓
          Planner
            ↓
      ExecutionPlan
```

`CapabilityRegistry` contains metadata only. `CapabilityActionBinder` validates that
each advertised capability maps to a registered action and an explicit safety policy.
Capability discovery does not grant execution authority.

## 15. Controlled Dependency Remediation

Project dependencies are discovered from `pyproject.toml` using read-only metadata
inspection. Missing Python dependencies become typed `install_python_package`
actions with explicit package context.

The remediation boundary is:

```text
Dependency Discovery
       ↓
AuditReport
       ↓
Planner
       ↓
ExecutionPlan
       ↓
Validator / SafetyGate
       ↓
Human Approval (REAL mutations)
       ↓
Real Handler
       ↓
Independent Verification
```

Real dependency handlers are narrowly scoped. They do not accept arbitrary shell
commands, shell strings, or arbitrary command-line arguments. Subprocess calls use
argument arrays and `shell=False`.

Safe mode never mutates the environment; it simulates remediation actions.

## 16. LLM Provider Boundary

The Agent provider contract supports three required deployment modes:

1. local HTTP server (LM Studio / OpenAI-compatible local servers, including Ollama
   deployments exposing the compatible API);
2. remote API with an API key supplied directly or from an environment variable;
3. in-process Python model/runtime.

Provider selection does not change Agent, Planner, Safety, or Executor contracts.

## 17. Verification Boundary

A successful handler result is not considered proof of the environment state.
Registered verifiers independently inspect the target state. Safe-mode simulated
results are explicitly marked `SKIPPED` for verification because no real state was
changed.
