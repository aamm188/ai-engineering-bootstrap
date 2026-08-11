# AI Engineering Bootstrap Roadmap

## Product Goal

Build a controlled AI Engineering Bootstrap platform that can inspect an engineering
environment, diagnose deficiencies, generate a deterministic remediation plan,
obtain required human approval, execute approved changes, independently verify the
result, recover from failures, and expose the same backend through a professional GUI.

## Frozen Execution Model

```text
Doctor
  ↓
AuditReport
  ↓
Agent / LLM Decision (optional decision layer)
  ↓
Planner
  ↓
ExecutionPlan
  ↓
Validation / Safety Gate
  ↓
Human Approval when required
  ↓
Executor / Real Handler
  ↓
Verification
  ↓
Recovery / Re-plan
```

Agent never executes actions directly. GUI and CLI never contain remediation business
logic.

## Completed Milestones

1. Doctor Foundation
2. Health Score
3. Model Unification
4. Categorization
5. CI/CD Output
6. Context-Aware Recommendations
7. Planner Foundation
8. Executor Foundation
9. Doctor → Planner → Executor Pipeline
10. Execution Plan Validation
11. Action Policy & Safety Gate
12. Real Action Handler Architecture
13. Controlled Real Execution — Phase 1
14. Post-Execution Verification Foundation
15. Retry / Failure / Re-plan Foundation
16. Capability / Tool Registry Foundation
17. Human Approval / Safety Controls
18. Agent / LLM Decision Layer Foundation
19. LLM Provider Integration
20. Agent Decision → Planner Integration
21. Capability → Action Contract Binding
22. Environment Dependency Discovery & Remediation Planning
23. Controlled Real Action Pack — Phase 1
24. Dependency Installation Workflow
25. Failure → Recovery → Re-plan Integration
26. Execution Audit & Run Evidence
27. Agent Runtime / Session Boundary

## Next Milestones

28. End-to-End Autonomous Environment Bootstrap
29. Engineering Environment Bootstrap + Cursor Integration
30. End-to-End Hardening & Security
31. Stable Backend API / Service Boundary
32. GUI Foundation
33. Professional GUI

## Milestones 25–27 Boundary

25. Recovery is bounded: a failed execution may trigger a fresh audit and deterministic re-plan, with validation and the same approval/safety boundary applied again. Re-plan count is explicitly capped.

26. Every pipeline run produces structured in-memory evidence containing ordered stage events, run identity, timestamps, recovery activity, and terminal status. Persistence is intentionally deferred.

27. Agent decisions run inside an explicit session boundary. The Agent runtime can decide and produce a plan, but exposes no execution capability and cannot bypass Planner, SafetyGate, Approval, Executor, or Verification.

## Cursor Boundary

Cursor is part of the engineering-environment bootstrap standard, not the runtime
Agent execution engine. Cursor installation, `.cursor/rules`, development tooling,
and developer-machine verification belong to milestone 29.

## Safety Rule

No generic shell execution capability is introduced as a shortcut. Real remediation
actions remain typed, narrowly scoped, policy-controlled, approval-aware, and
independently verifiable.
