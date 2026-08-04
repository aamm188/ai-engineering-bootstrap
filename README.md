# AI Engineering Bootstrap

AI Engineering Bootstrap is a deterministic Python 3.12 command-line application for checking a local engineering environment and creating projects from predefined templates.

## Phase 1 scope

The application will provide two independent capabilities behind one CLI:

- A read-only audit of the operating system, running Python interpreter, Git, Docker, and best-effort GPU availability.
- Safe project generation from `ai-app-template-v1`. The other Phase 1 template identifiers remain reserved for later implementation.

The CLI will use Typer for commands and Rich for human-readable output. Application services, typed models, and side-effecting adapters remain separate as documented in `docs/architecture.md` and the accepted ADRs.

## Commands

```text
ai-bootstrap audit [--format table|json]
ai-bootstrap doctor
ai-bootstrap list-templates
ai-bootstrap create-project PROJECT_NAME --template TEMPLATE_NAME
```

The audit and doctor commands are read-only. Project creation writes a new folder in the current directory and fails if that folder already exists.

## Development baseline

- Python 3.12 or newer
- Source layout under `src/`
- pytest for tests
- Ruff for linting and formatting
- Type hints and docstrings for public interfaces

The configured development commands are:

```text
make install
make lint
make format
make test
```

## Safety and exclusions

Audits report conditions without installing, configuring, starting, stopping, or modifying host software. Generation will validate input, reject an existing target, and avoid leaving partial output.

GitHub provisioning, CI/CD and Dev Container generation, LLM integration, tool calling, autonomous workflows, and multi-agent behavior are outside Phase 1.

## Status

Phase 1 currently includes the audit CLI and `ai-app-template-v1` project generation.

## Documentation Index

The following documents define the project architecture and development process.

| Document | Purpose |
|----------|---------|
| docs/architecture.md | System architecture |
| docs/roadmap.md | Project roadmap |
| docs/development/git-workflow.md | Git workflow |
| docs/development/github-setup.md | GitHub & SSH setup |
| docs/development/coding-standards.md | Coding standards |
| docs/development/bootstrap-process.md | Environment bootstrap and doctor command |
| ADR/ | Architecture Decision Records |

These documents are the primary entry points for understanding the project.
