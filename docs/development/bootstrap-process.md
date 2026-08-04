# Bootstrap Process

This document describes the bootstrap process for setting up a development environment for the AI Engineering Bootstrap project.

## Overview

The project provides two read-only diagnostic commands to help developers validate their environment:

1. **`ai-bootstrap audit`** - Comprehensive environment audit with JSON or table output
2. **`ai-bootstrap doctor`** - Human-friendly environment validation report (primary entry point)

## Environment Doctor Command

### Purpose

The `ai-bootstrap doctor` command is the primary entry point for validating a developer environment before running any other project commands. It performs a comprehensive check of the local development setup and provides actionable recommendations.

### Usage

```bash
ai-bootstrap doctor
```

### Checks Performed

The doctor command validates the following aspects of your environment:

| Check | Description |
|-------|-------------|
| Python version | Verifies the running Python interpreter |
| Virtual Environment | Confirms execution inside a virtual environment |
| Editable Installation | Checks if the package is installed in editable mode |
| Required Packages | Validates installation of typer, rich, pytest, and ruff |
| Git Executable | Confirms Git is available in PATH |
| Docker Executable | Confirms Docker is available in PATH |
| Operating System | Reports OS name and version |
| Platform | Identifies Windows, Linux, or macOS |

### Output Format

The command produces a human-friendly report using Rich tables:

```
Environment Doctor

Python ............... OK
Virtual Environment .. OK
Editable Install ..... Missing
Typer ................ OK
Rich ................. OK
Pytest ............... Missing
Ruff ................. OK
Git .................. OK
Docker ............... Missing
OS ................... Windows 11

Environment NOT Ready

Recommendations:
  python -m venv .venv
  python -m pip install -e "."
  # Install Docker: https://docs.docker.com/get-docker/
```

### Read-Only Behavior

**Important:** The `doctor` command is completely read-only. It will never:

- Install packages
- Modify files
- Create directories
- Change git configuration
- Execute shell scripts
- Request sudo privileges

The command only inspects the environment and prints a report. Recommendations are displayed as text only and must be executed manually by the user.

### Exit Status

- Exit code `0`: Command completed successfully (regardless of check results)
- The output indicates whether the environment is ready or not

## Audit Command

For machine-readable output, use the audit command:

```bash
ai-bootstrap audit --format json
ai-bootstrap audit --format table
```

## Recommendations

When checks fail, the doctor command provides specific recommendations:

| Failed Check | Recommendation |
|--------------|----------------|
| Virtual Environment | `python -m venv .venv` |
| Editable Install | `python -m pip install -e "."` |
| Missing Package | `python -m pip install <package-name>` |
| Missing Git | Install Git from https://git-scm.com/ |
| Missing Docker | Install Docker from https://docs.docker.com/get-docker/ |

## Limitations

- The doctor command does not automatically fix issues
- GPU detection is best-effort and may not work on all systems
- Some checks may have limited accuracy on certain platforms
- Network-dependent checks (like Docker Hub connectivity) are not performed

## Future Enhancements

Automatic installation and configuration features are planned for a future "Bootstrap Planner" phase but are intentionally excluded from this read-only implementation.
