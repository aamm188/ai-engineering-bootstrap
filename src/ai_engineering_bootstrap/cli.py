"""Typer command-line interface for AI Engineering Bootstrap."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import typer
from rich.console import Console
from rich.table import Table

from ai_engineering_bootstrap.audit import default_audit_service, doctor_audit_service
from ai_engineering_bootstrap.exceptions import BootstrapError
from ai_engineering_bootstrap.generation import (
    default_project_generator,
    default_template_catalog,
)
from ai_engineering_bootstrap.models import AuditReport, GenerationRequest

app = typer.Typer(
    name="ai-bootstrap",
    help="Audit an AI engineering environment.",
    no_args_is_help=True,
)
console = Console()


def _report_data(report: AuditReport) -> dict[str, list[dict[str, object]]]:
    """Convert an audit report into deterministic JSON-compatible data."""
    return {
        "checks": [
            {
                "name": check.name,
                "status": check.status.value,
                "facts": check.facts,
                "diagnostic": check.diagnostic,
            }
            for check in report.checks
        ]
    }


def _render_table(report: AuditReport) -> None:
    """Render an audit report for interactive use."""
    table = Table(title="Environment Audit")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Details")
    for check in report.checks:
        details = ", ".join(f"{key}: {value}" for key, value in check.facts.items())
        if check.diagnostic:
            details = check.diagnostic
        table.add_row(check.name, check.status.value, details)
    console.print(table)


def _render_doctor_report(report: AuditReport) -> None:
    """Render the Environment Doctor report with summary and recommendations."""
    console.print()
    console.print("[bold]Environment Doctor[/bold]")
    console.print()

    # Build status map for recommendations
    failed_checks: list[str] = []

    for check in report.checks:
        status_str = (
            "OK"
            if check.status == "available"
            else check.status.value.replace("_", " ").title()
        )

        # Determine display name
        display_name = check.name.replace("_", " ").title()

        # Map to expected output format
        if check.name == "python":
            display_name = "Python"
        elif check.name == "virtual_environment":
            display_name = "Virtual Environment"
        elif check.name == "editable_install":
            display_name = "Editable Install"
        elif check.name == "typer":
            display_name = "Typer"
        elif check.name == "rich":
            display_name = "Rich"
        elif check.name == "pytest":
            display_name = "Pytest"
        elif check.name == "ruff":
            display_name = "Ruff"
        elif check.name == "git":
            display_name = "Git"
        elif check.name == "docker":
            display_name = "Docker"
        elif check.name == "operating_system":
            # Extract OS info from facts
            os_name = check.facts.get("name", "Unknown")
            os_release = check.facts.get("release", "")
            if os_release:
                display_name = f"{os_name} {os_release}"
            else:
                display_name = os_name
            status_str = "OK"  # OS check always passes if we get here

        if check.status != "available":
            failed_checks.append(check.name)
            console.print(f"{display_name} .. [red]{status_str}[/red]")
        else:
            console.print(f"{display_name} .. [green]OK[/green]")

    # Print OS line separately if not already printed
    os_check = next((c for c in report.checks if c.name == "operating_system"), None)
    if os_check and os_check.status == "available":
        os_name = os_check.facts.get("name", "Unknown")
        os_release = os_check.facts.get("release", "")
        os_display = f"{os_name} {os_release}".strip()
        console.print(f"OS ............... [green]{os_display}[/green]")

    console.print()

    # Summary
    if not failed_checks:
        console.print("[bold green]Environment Ready[/bold green]")
    else:
        console.print("[bold red]Environment NOT Ready[/bold red]")
        console.print()
        console.print("[bold]Recommendations:[/bold]")
        _print_recommendations(failed_checks)


def _print_recommendations(failed_checks: list[str]) -> None:
    """Print recommended commands for failed checks."""
    recommendations: list[str] = []

    if "virtual_environment" in failed_checks:
        recommendations.append("python -m venv .venv")

    if "editable_install" in failed_checks or any(
        pkg in failed_checks for pkg in ["typer", "rich", "pytest", "ruff"]
    ):
        recommendations.append('python -m pip install -e ".[dev]"')

    if "git" in failed_checks:
        recommendations.append("# Install Git: https://git-scm.com/downloads")

    if "docker" in failed_checks:
        recommendations.append("# Install Docker: https://docs.docker.com/get-docker/")

    for rec in recommendations:
        console.print(f"  {rec}")


@app.command()
def audit(
    output_format: Literal["table", "json"] = typer.Option(
        "table",
        "--format",
        help="Output format.",
    ),
) -> None:
    """Run a read-only audit of the local engineering environment."""
    report = default_audit_service().run()
    if output_format == "json":
        typer.echo(json.dumps(_report_data(report), sort_keys=True))
        return
    _render_table(report)


@app.command()
def doctor() -> None:
    """Validate the developer environment before running other commands.

    This command is completely read-only. It never installs packages,
    modifies files, creates directories, changes git configuration,
    executes shell scripts, or requests sudo.
    """
    report = doctor_audit_service().run()
    _render_doctor_report(report)


@app.command("list-templates")
def list_templates() -> None:
    """List template identifiers discovered in the template directory."""
    templates = default_template_catalog().list_templates()
    if not templates:
        typer.echo("No templates found.")
        return
    for template in templates:
        typer.echo(template.template_id)


@app.command("create-project")
def create_project(
    project_name: str = typer.Argument(..., help="Name of the project to create."),
    template_name: str = typer.Option(..., "--template", help="Template identifier."),
) -> None:
    """Create a project from a template without overwriting existing files."""
    try:
        result = default_project_generator().generate(
            GenerationRequest(
                project_name=project_name,
                template_id=template_name,
                destination=Path.cwd(),
            )
        )
    except BootstrapError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Created project: {result.project_path}")


if __name__ == "__main__":
    app()
