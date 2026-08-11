"""Tests for milestones 25-27: recovery, evidence, and Agent sessions."""

from unittest.mock import MagicMock, patch

from ai_engineering_bootstrap.agent.engine import AgentDecisionEngine
from ai_engineering_bootstrap.agent.planning import AgentPlanningService
from ai_engineering_bootstrap.agent.provider import MockProvider
from ai_engineering_bootstrap.agent.runtime import AgentRuntime, AgentSessionStatus
from ai_engineering_bootstrap.audit.models import (
    AuditCheck,
    AuditReport,
    CheckCategory,
    CheckStatus,
    EnvironmentReadiness,
)
from ai_engineering_bootstrap.executor.capability import default_capability_registry
from ai_engineering_bootstrap.executor.models import (
    ActionResult,
    ExecutionResult,
    ExecutionStatus,
)
from ai_engineering_bootstrap.pipeline import PipelineEngine
from ai_engineering_bootstrap.planner.engine import PlannerEngine
from ai_engineering_bootstrap.planner.models import ExecutionPlan, ExecutionPlanAction


def _report(passed: bool) -> AuditReport:
    checks = [
        AuditCheck(
            name="Git",
            status=CheckStatus.PASSED if passed else CheckStatus.FAILED,
            category=CheckCategory.TOOLS,
        )
    ]
    return AuditReport(checks=checks, readiness=EnvironmentReadiness.calculate(checks))


def _plan(action_id: str) -> ExecutionPlan:
    return ExecutionPlan(True, [ExecutionPlanAction(action_id, action_id, 1)])


def test_pipeline_replans_once_after_replanable_failure() -> None:
    first = _plan("unknown_action")
    second = _plan("check_python_version_real")
    failed = ExecutionResult(
        False,
        [ActionResult("unknown_action", ExecutionStatus.FAILED, "Action is unknown")],
        "failed",
    )
    succeeded = ExecutionResult(
        True,
        [ActionResult("check_python_version_real", ExecutionStatus.SUCCESS, "ok")],
        "ok",
    )

    with (
        patch("ai_engineering_bootstrap.pipeline.engine.default_audit_service") as audit_factory,
        patch("ai_engineering_bootstrap.pipeline.engine.PlannerEngine") as planner_cls,
        patch("ai_engineering_bootstrap.pipeline.engine.ExecutorEngine") as executor_cls,
        patch("ai_engineering_bootstrap.pipeline.engine.ExecutionPlanValidator") as validator_cls,
    ):
        audit = MagicMock()
        audit.run.side_effect = [_report(False), _report(True)]
        audit_factory.return_value = audit
        planner = MagicMock()
        planner.generate_plan.side_effect = [first, second]
        planner_cls.return_value = planner
        validator_cls.return_value.validate.return_value = MagicMock(is_valid=True)
        executor = MagicMock()
        executor.execute.side_effect = [failed, succeeded]
        executor.verify.side_effect = [[], []]
        executor_cls.return_value = executor

        result = PipelineEngine().run(max_replans=1)

    assert result.replan_requested is True
    assert result.replan_count == 1
    assert result.replanned_plan == second
    assert result.execution_result == succeeded
    assert len(result.execution_history) == 2
    assert planner.generate_plan.call_count == 2
    assert audit.run.call_count == 2


def test_pipeline_replan_limit_prevents_unbounded_recovery() -> None:
    plan = _plan("unknown_action")
    failed = ExecutionResult(
        False,
        [ActionResult("unknown_action", ExecutionStatus.FAILED, "Action is unknown")],
        "failed",
    )

    with (
        patch("ai_engineering_bootstrap.pipeline.engine.default_audit_service") as audit_factory,
        patch("ai_engineering_bootstrap.pipeline.engine.PlannerEngine") as planner_cls,
        patch("ai_engineering_bootstrap.pipeline.engine.ExecutorEngine") as executor_cls,
        patch("ai_engineering_bootstrap.pipeline.engine.ExecutionPlanValidator") as validator_cls,
    ):
        audit = MagicMock()
        audit.run.return_value = _report(False)
        audit_factory.return_value = audit
        planner = MagicMock()
        planner.generate_plan.return_value = plan
        planner_cls.return_value = planner
        validator_cls.return_value.validate.return_value = MagicMock(is_valid=True)
        executor = MagicMock()
        executor.execute.return_value = failed
        executor.verify.return_value = []
        executor_cls.return_value = executor

        result = PipelineEngine().run(max_replans=0)

    assert result.replan_count == 0
    assert result.replan_requested is True
    assert executor.execute.call_count == 1
    assert audit.run.call_count == 1


def test_pipeline_records_ordered_run_evidence() -> None:
    plan = _plan("check_python_version_real")
    success = ExecutionResult(
        True,
        [ActionResult("check_python_version_real", ExecutionStatus.SUCCESS, "ok")],
        "ok",
    )

    with (
        patch("ai_engineering_bootstrap.pipeline.engine.default_audit_service") as audit_factory,
        patch("ai_engineering_bootstrap.pipeline.engine.PlannerEngine") as planner_cls,
        patch("ai_engineering_bootstrap.pipeline.engine.ExecutorEngine") as executor_cls,
    ):
        audit = MagicMock()
        audit.run.return_value = _report(True)
        audit_factory.return_value = audit
        planner_cls.return_value.generate_plan.return_value = plan
        executor = MagicMock()
        executor.execute.return_value = success
        executor.verify.return_value = []
        executor_cls.return_value = executor

        result = PipelineEngine().run(run_id="run-evidence-1")

    evidence = result.run_evidence
    assert evidence.run_id == "run-evidence-1"
    assert evidence.completed_at is not None
    assert [event.sequence for event in evidence.events] == list(range(1, len(evidence.events) + 1))
    stages = [event.stage for event in evidence.events]
    assert stages[:4] == ["audit", "audit", "planning", "validation"]
    assert stages[-1] == "pipeline"


def test_agent_runtime_creates_bounded_completed_session() -> None:
    registry = default_capability_registry()
    service = AgentPlanningService(
        AgentDecisionEngine(MockProvider(), registry), PlannerEngine(), registry
    )

    result = AgentRuntime(service).run("fix environment", run_id="run-agent-1")

    assert result.session.run_id == "run-agent-1"
    assert result.session.status == AgentSessionStatus.COMPLETED
    assert result.planning.decision.selected_capability_ids
    assert result.planning.plan.is_actionable


def test_agent_runtime_never_exposes_execution_capability() -> None:
    registry = default_capability_registry()
    service = AgentPlanningService(
        AgentDecisionEngine(MockProvider(), registry), PlannerEngine(), registry
    )
    runtime = AgentRuntime(service)

    assert not hasattr(runtime, "execute")
    assert not hasattr(runtime, "run_shell")
    assert not hasattr(runtime, "safety_gate")
