# Architecture

## Scope

Phase 1 is a deterministic Python 3.12 CLI with three use cases: read-only environment auditing, environment validation via the Environment Doctor, and project generation from three predefined templates. The capabilities share presentation and domain conventions but remain independently coordinated.

## Dependency direction

```text
CLI / Rich presentation
    -> application services
        -> typed protocols and domain models
            <- infrastructure adapters
```

- `cli.py` parses commands, invokes services, formats results, and maps expected failures to stable exit codes.
- `audit.py` coordinates the audit use case and provides the doctor command entry point without presentation logic.
- `generation.py` coordinates project generation without presentation logic.
- `models.py` defines typed requests and results without printing or filesystem access.
- `probes/` isolates platform and subprocess inspection for both audit and doctor functionality.
- Template resource access and filesystem writes belong to generation infrastructure.

Dependencies are explicit. Phase 1 does not use global state, a dependency-injection container, repository pattern, plug-in system, or agent framework.

## Side-effect boundaries

Audit probes may inspect standard-library platform facts and run non-mutating executable checks using argument arrays, captured output, timeouts, and no shell. Individual failures become typed results and do not stop unrelated probes.

Generation validates identifiers, project names, paths, and destination non-existence before writing. It stages output within the destination parent, substitutes only declared variables in declared UTF-8 text files, preserves binary bytes, cleans up failures, and performs an atomic final rename where feasible.

## Stable Phase 1 contracts

- Audit statuses: `available`, `not_found`, `unsupported`, and `error`.
- Template identifiers: `ai-app-template-v1`, `ml-template-v1`, and `ai-research-template-v1`.
- Destination policy: fail when the target exists; no merge or overwrite mode.
- CLI commands: `ai-bootstrap audit`, `ai-bootstrap doctor`, `ai-bootstrap list-templates`, and `ai-bootstrap create-project PROJECT_NAME --template TEMPLATE_NAME`.

Changes to accepted interfaces, models, commands, output behavior, or collision semantics require a new or superseding ADR.

## Exclusions

Phase 1 excludes GitHub provisioning, CI/CD generation, Dev Container generation, LLM integration, tool calling, autonomous workflows, and multi-agent architecture.
