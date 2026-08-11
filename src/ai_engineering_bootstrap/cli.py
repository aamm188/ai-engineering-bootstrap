#!/usr/bin/env python3
"""Typer command-line interface for AI Engineering Bootstrap."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import typer
from rich.console import Console
from rich.table import Table

from ai_engineering_bootstrap.audit import default_audit_service
from ai_engineering_bootstrap.audit.models import AuditReport, CheckStatus
from ai_engineering_bootstrap.exceptions import BootstrapError
from ai_engineering_bootstrap.executor import ExecutorEngine
from ai_engineering_bootstrap.generation import (
    default_project_generator,
    default_template_catalog,
)
from ai_engineering_bootstrap.models import GenerationRequest
from ai_engineering_bootstrap.pipeline import PipelineEngine
from ai_engineering_bootstrap.planner import PlannerEngine

app = typer.Typer(
    name="ai-bootstrap",
    help="Audit an AI engineering environment.",
    no_args_is_help=True,
)
console = Console()


def _report_data(report: AuditReport) -> dict[str, Any]:
    """Convert an audit report into deterministic JSON-compatible data."""
    return {
        "checks": [
            {
                "name": check.name,
                "status": check.status.value,
                "category": check.category.value,
                "facts": check.facts,
                "details": check.details,
                "recommendations": check.recommendations,
            }
            for check in report.checks
        ],
        "readiness": {
            "development_ready": report.readiness.development_ready,
            "production_ready": report.readiness.production_ready,
            "health_score": report.readiness.health_score,
            "passed": report.readiness.passed_count,
            "failed": report.readiness.failed_count,
            "warnings": report.readiness.warning_count,
        }
    }


def _render_table(report: AuditReport) -> None:
    """Render an audit report for interactive use (Legacy flat view)."""
    table = Table(title="Environment Audit")
    table.add_column("Category")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Details")

    for check in report.checks:
        status_str = "OK" if check.status == CheckStatus.PASSED else "FAILED"
        if check.status == CheckStatus.WARNING:
            status_str = "WARNING"
        table.add_row(
            check.category.value,
            check.name,
            status_str,
            check.details
        )
    console.print(table)


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
        exit_code = 0 if report.readiness.development_ready else 1
        typer.echo(json.dumps(_report_data(report), sort_keys=True, indent=2))
        raise typer.Exit(code=exit_code)
    _render_table(report)


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


@app.command()
def doctor() -> None:
    """Run a read-only environment health check (Environment Doctor V3)."""
    audit_service = default_audit_service()
    report = audit_service.run()

    grouped_checks: dict[str, list] = {}
    for check in report.checks:
        cat = check.category.value
        if cat not in grouped_checks:
            grouped_checks[cat] = []
        grouped_checks[cat].append(check)

    for category, checks in grouped_checks.items():
        table = Table(title=f"[bold cyan]{category}[/bold cyan]")
        table.add_column("Check", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Details", style="white")

        for check in checks:
            status_str = "OK" if check.status == CheckStatus.PASSED else "FAILED"
            if check.status == CheckStatus.WARNING:
                status_str = "WARNING"

            details = check.details
            if not details:
                details = check.facts.get("version", check.facts.get("current", ""))

            table.add_row(check.name, status_str, details)

        console.print(table)
        console.print()

    r = report.readiness
    dev_status_str = "[green]YES[/green]" if r.development_ready else "[red]NO[/red]"
    prod_status_str = "[green]YES[/green]" if r.production_ready else "[red]NO[/red]"

    console.rule("[bold]Summary[/bold]")
    console.print(f"[bold]Development Ready :[/bold] {dev_status_str}")
    console.print(f"[bold]Production Ready :[/bold] {prod_status_str}")
    console.print(f"[bold]Health Score      :[/bold] {r.health_score}/100")
    console.print(f"[bold]Passed :[/bold] {r.passed_count}  [bold]Failed :[/bold] {r.failed_count}  [bold]Warnings :[/bold] {r.warning_count}")

    all_recommendations = set()
    for check in report.checks:
        for rec in check.recommendations:
            all_recommendations.add(rec)

    console.print()
    if all_recommendations:
        console.print("[yellow bold]Recommended actions:[/yellow bold]")
        for rec in sorted(all_recommendations):
            console.print(f"• {rec}")
    else:
        console.print("[green bold]No Actions Required[/green bold]")
        console.print("Environment already satisfies the project requirements.")


@app.command()
def plan() -> None:
    """Generate an execution plan based on the latest audit."""
    audit_service = default_audit_service()
    report = audit_service.run()
    engine = PlannerEngine()
    plan = engine.generate_plan(report)
    if not plan.is_actionable:
        console.print("[green]✓ Environment is healthy. No actions required.[/green]")
        return

    console.print("[bold]Execution Plan:[/bold]\n")
    for i, action in enumerate(plan.actions, 1):
        console.print(f"{i}. [cyan]{action.description}[/cyan]")
        console.print(f"   [dim]ID: {action.action_id} | Priority: {action.priority}[/dim]")
        console.print()


@app.command()
def execute() -> None:
    """
    Execute the generated plan (SAFE MODE / DRY RUN).

    WARNING: This is a foundation feature.
    NO real system changes will be made.
    Actions are simulated to verify the execution pipeline.
    """
    audit_service = default_audit_service()
    report = audit_service.run()

    # Generate plan
    planner = PlannerEngine()
    plan = planner.generate_plan(report)

    if not plan.is_actionable:
        console.print("[green]✓ Environment is healthy. No actions to execute.[/green]")
        return

    console.print("[yellow bold]⚠️ SAFE MODE ACTIVE[/yellow bold]")
    console.print("The following actions would be taken, but are currently simulated:")
    console.print()

    # Execute plan
    executor = ExecutorEngine()
    result = executor.execute(plan)

    # Display results
    for res in result.results:
        status_color = (
            "green"
            if res.status.value == "success"
            else ("red" if res.status.value == "failed" else "yellow")
        )
        status_str = res.status.value.upper()
        console.print(f"[{status_color}]• [{status_str}] {res.action_id}[/{status_color}]")
        console.print(f"  [dim]{res.message}[/dim]")

    console.print()
    final_color = "green" if result.is_success else "red"
    console.print(f"[{final_color} bold]{result.summary}[/{final_color} bold]")
    console.print(
        "\n[dim]Note: Real system modification handlers are not yet implemented.[/dim]"
    )


@app.command()
def run_pipeline(
    real_execution: bool = typer.Option(
        False,
        "--real-execution",
        help="Enable REAL execution mode.",
    ),
    interactive_approval: bool = typer.Option(
        False,
        "--interactive-approval",
        help="Prompt for required human approvals before REAL execution.",
    ),
) -> None:
    from ai_engineering_bootstrap.executor.mode import ExecutionMode
    mode = ExecutionMode.REAL if real_execution else ExecutionMode.SAFE
    console.print(f"[bold cyan]Running Full Pipeline ({mode.value.upper()} MODE)...[/bold cyan]\n")
    if mode == ExecutionMode.REAL:
        console.print("[yellow bold]⚠️ REAL EXECUTION MODE ACTIVE[/yellow bold]")
        console.print("Only pre-approved, non-destructive actions will run.\n")
    engine = PipelineEngine()
    approval_provider = None
    run_id = "cli-run"
    pending_approvals = None
    if interactive_approval:
        if not real_execution:
            raise typer.BadParameter("--interactive-approval requires --real-execution")
        from ai_engineering_bootstrap.approval.provider import InMemoryApprovalProvider
        approval_provider = InMemoryApprovalProvider()

    result = engine.run(
        mode=mode,
        approval_provider=approval_provider,
        pending_approvals=pending_approvals,
        run_id=run_id,
    )

    if interactive_approval and result.is_pending_approval:
        approval_ids: dict[str, list[str]] = {}
        for request in result.approval_requests:
            approval_target = request.reason or request.action_id
            answer = typer.confirm(
                f"Approve {approval_target} ({request.risk_level})?",
                default=False,
            )
            if answer:
                approval_provider.approve(request.approval_id)
            else:
                approval_provider.reject(request.approval_id)
            approval_ids.setdefault(request.action_id, []).append(request.approval_id)

        result = engine.run(
            mode=mode,
            approval_provider=approval_provider,
            pending_approvals=approval_ids,
            run_id=run_id,
        )
    # 1. Audit
    r = result.audit_report.readiness
    console.print(f"[bold]1. Audit Complete:[/bold] Health Score {r.health_score}/100")
    # 2. Plan
    if result.original_plan.is_actionable:
        console.print(f"[bold]2. Plan Generated:[/bold] {len(result.original_plan.actions)} action(s).")
    else:
        console.print("[bold]2. Plan Generated:[/bold] No actions required.")
    # 3. Validation
    if result.validation_result.is_valid:
        console.print("[bold]3. Validation:[/bold] [green]PASSED[/green]")
    else:
        console.print("[bold]3. Validation:[/bold] [red]FAILED[/red]")
        for err in result.validation_result.errors:
            console.print(f"   - {err}")
        console.print("\n[red bold]Pipeline halted.[/red bold]")
        return
    # 4. Execution
    if result.execution_result:
        if result.execution_result.is_success:
             console.print("[bold]4. Execution:[/bold] [green]SUCCESS[/green]")
        else:
             console.print("[bold]4. Execution:[/bold] [red]FAILED[/red]")
        for res in result.execution_result.results:
            color = "green" if res.status.value == "success" else ("red" if res.status.value == "failed" else "yellow")
            console.print(f"   [{color}]• [{res.status.value.upper()}] {res.action_id}[/{color}]")
            console.print(f"      [dim]{res.message}[/dim]")
    else:
        console.print("[bold]4. Execution:[/bold] [dim]Skipped (Validation Failed)[/dim]")
    # 5. Verification
    # اصلاح: استفاده از getattr برای جلوگیری از خطا در صورت عدم وجود فیلد
    # و بررسی نام صحیح فیلد (احتمالاً verification_result به صورت مفرد یا جمع)
    console.print()
    # تلاش برای دریافت لیست نتایج تأیید با نام‌های محتمل
    verification_results = getattr(result, 'verification_results', None)
    if verification_results is None:
        verification_results = getattr(result, 'verification_result', None)
    # اگر لیست نبود و یک تک نتیجه بود، آن را به لیست تبدیل کن
    if verification_results and not isinstance(verification_results, list):
        verification_results = [verification_results]

    if verification_results:
        all_skipped = all(v.status.value == "skipped" for v in verification_results)
        all_verified = all(v.status.value != "failed" for v in verification_results)
        if all_skipped:
            console.print("[bold]5. Verification:[/bold] [dim]SKIPPED[/dim]")
        elif all_verified:
            console.print("[bold]5. Verification:[/bold] [green]COMPLETED[/green]")
        else:
            console.print("[bold]5. Verification:[/bold] [red]ISSUES DETECTED[/red]")
        for v in verification_results:
            color = "green" if v.status.value == "verified" else ("red" if v.status.value == "failed" else "yellow")
            console.print(f"   [{color}]• [{v.status.value.upper()}] {v.action_id}[/{color}]")
            console.print(f"      [dim]{v.message}[/dim]")
            if hasattr(v, 'observed') and v.observed:
                console.print(f"      [dim]Observed: {v.observed}[/dim]")
    else:
        console.print("[bold]5. Verification:[/bold] [dim]No actions to verify[/dim]")
    console.print()
    if result.is_success:
        console.print("[green bold]✓ Pipeline Completed Successfully.[/green bold]")
    else:
        console.print("[red bold]⚠ Pipeline Completed with Issues.[/red bold]")
        raise typer.Exit(code=1)


@app.command()
def bootstrap() -> None:
    """Run audit, display plan, and (in future) execute fixes."""
    # فعلاً فقط audit و plan را نمایش می‌دهد
    audit_service = default_audit_service()
    report = audit_service.run()
    # نمایش خلاصه دکتر
    r = report.readiness
    if r.development_ready:
        console.print("[green]Environment is ready.[/green]")
    else:
        console.print("[red]Environment needs attention. Generating plan...[/red]")
        engine = PlannerEngine()
        plan = engine.generate_plan(report)
        if plan.is_actionable:
            console.print("\n[bold]Required Actions:[/bold]")
            for action in plan.actions:
                console.print(f"• {action.description}")


if __name__ == "__main__":
    app()
