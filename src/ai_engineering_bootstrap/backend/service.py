"""Stable application service boundary for CLI and GUI consumers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from ai_engineering_bootstrap.approval.provider import InMemoryApprovalProvider
from ai_engineering_bootstrap.audit import default_audit_service
from ai_engineering_bootstrap.bootstrap import EnvironmentBootstrapService
from ai_engineering_bootstrap.engineering import EngineeringEnvironmentService
from ai_engineering_bootstrap.executor.mode import ExecutionMode
from ai_engineering_bootstrap.pipeline import PipelineEngine, PipelineResult
from ai_engineering_bootstrap.planner import PlannerEngine
from ai_engineering_bootstrap.planner.models import ExecutionPlan, ExecutionPlanAction


def _check_dict(check: Any) -> dict[str, Any]:
    return {
        "name": check.name,
        "status": check.status.value,
        "category": check.category.value,
        "details": check.details,
        "facts": check.facts,
        "recommendations": check.recommendations,
    }


def _audit_dict(report: Any) -> dict[str, Any]:
    return {
        "checks": [_check_dict(check) for check in report.checks],
        "readiness": {
            "development_ready": report.readiness.development_ready,
            "production_ready": report.readiness.production_ready,
            "passed": report.readiness.passed_count,
            "failed": report.readiness.failed_count,
            "warnings": report.readiness.warning_count,
            "health_score": report.readiness.health_score,
        },
    }


def _plan_dict(plan: Any) -> dict[str, Any]:
    return {
        "plan_id": plan.plan_id,
        "is_actionable": plan.is_actionable,
        "summary": plan.summary,
        "actions": [
            {
                "action_id": action.action_id,
                "description": action.description,
                "priority": action.priority,
                "context": action.context,
            }
            for action in plan.actions
        ],
    }


def _pipeline_dict(result: PipelineResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "success": result.is_success,
        "audit": _audit_dict(result.audit_report),
        "plan": _plan_dict(result.original_plan),
        "validation": {
            "is_valid": result.validation_result.is_valid,
            "errors": result.validation_result.errors,
            "warnings": result.validation_result.warnings,
        },
        "execution": None,
        "verification": None,
        "recovery": {
            "replan_requested": result.replan_requested,
            "replan_count": result.replan_count,
            "failure_records": [
                {
                    "action_id": record.action_id,
                    "failure_type": record.failure_type.value,
                    "message": record.message,
                    "retryable": record.is_retryable,
                    "requires_replan": record.requires_replan,
                    "details": record.details or {},
                }
                for record in result.failure_records
            ],
        },
        "agent": None,
        "evidence": result.run_evidence.to_dict() if result.run_evidence else None,
    }
    if result.execution_result is not None:
        payload["execution"] = {
            "success": result.execution_result.is_success,
            "summary": result.execution_result.summary,
            "results": [
                {
                    "action_id": item.action_id,
                    "status": item.status.value,
                    "message": item.message,
                    "details": item.details,
                }
                for item in result.execution_result.results
            ],
        }
    if result.verification_result is not None:
        payload["verification"] = [
            {
                "action_id": item.action_id,
                "status": item.status.value,
                "message": item.message,
                "expected": item.expected,
                "observed": item.observed,
                "details": item.details,
            }
            for item in result.verification_result
        ]
    if result.agent_decision is not None:
        payload["agent"] = {
            "decision_id": result.agent_decision.decision_id,
            "reasoning_summary": result.agent_decision.reasoning_summary,
            "selected_capability_ids": result.agent_decision.selected_capability_ids,
            "confidence": result.agent_decision.confidence,
            "metadata": result.agent_decision.metadata,
        }
    return payload


@dataclass(frozen=True)
class BackendResult:
    """Stable response envelope exposed by the application service boundary."""

    data: dict[str, Any]
    request_id: str
    status: str = "ok"


@dataclass
class BootstrapSession:
    """State for one explicit GUI-controlled bootstrap run."""

    session_id: str
    run_id: str
    plan: ExecutionPlan
    provider: InMemoryApprovalProvider
    approval_ids: dict[str, str]
    statuses: dict[str, str] = field(default_factory=dict)
    results: dict[str, dict[str, Any]] = field(default_factory=dict)


class ApplicationBackend:
    """Expose application use cases without duplicating domain logic."""

    VERSION = "v1"
    _sessions: dict[str, BootstrapSession] = {}

    @staticmethod
    def _request_id() -> str:
        return f"req-{uuid4()}"

    @staticmethod
    def _result(data: dict[str, Any], status: str = "ok") -> BackendResult:
        return BackendResult(data=data, request_id=ApplicationBackend._request_id(), status=status)

    def health(self) -> BackendResult:
        return self._result(
            {
                "status": "ok",
                "version": self.VERSION,
                "capabilities": {
                    "audit": True,
                    "plan": True,
                    "engineering": True,
                    "safe_run": True,
                    "safe_bootstrap": True,
                    "bootstrap_session": True,
                    "real_run": False,
                },
            }
        )

    def audit(self) -> BackendResult:
        return self._result(_audit_dict(default_audit_service().run()))

    def plan(self) -> BackendResult:
        report = default_audit_service().run()
        return self._result(_plan_dict(PlannerEngine().generate_plan(report)))

    def engineering(self) -> BackendResult:
        report = EngineeringEnvironmentService().run()
        return self._result(
            {
                "project_root": str(report.project_root),
                "ready": report.is_ready,
                "required_tools_ready": report.required_tools_ready,
                "cursor_rules_present": report.cursor_rules_present,
                "cursor_available": report.cursor_available,
                "tools": [
                    {
                        "name": tool.name,
                        "required": tool.required,
                        "available": tool.available,
                        "path": tool.path,
                    }
                    for tool in report.tools
                ],
            }
        )

    def run_safe(self) -> BackendResult:
        result = PipelineEngine().run(mode=ExecutionMode.SAFE, run_id=f"backend-safe-{uuid4()}")
        return self._result(_pipeline_dict(result))

    def bootstrap_safe(self) -> BackendResult:
        result = EnvironmentBootstrapService().run(
            mode=ExecutionMode.SAFE,
            run_id=f"backend-bootstrap-{uuid4()}",
        )
        return self._result(_pipeline_dict(result.pipeline_result))

    def run_real_requires_cli(self) -> BackendResult:
        return self._result(
            {
                "allowed": False,
                "message": "Use an explicit bootstrap session and approve each real action individually.",
            },
            status="rejected",
        )

    def start_bootstrap_session(self) -> BackendResult:
        run_id = f"gui-bootstrap-{uuid4()}"
        provider = InMemoryApprovalProvider()
        result = PipelineEngine().run(
            mode=ExecutionMode.REAL,
            approval_provider=provider,
            pending_approvals={},
            run_id=run_id,
        )
        if not result.is_pending_approval:
            return self._result(
                {"state": "completed", "pipeline": _pipeline_dict(result)},
            )

        approval_ids = {request.action_id: request.approval_id for request in result.approval_requests}
        session_id = f"session-{uuid4()}"
        session = BootstrapSession(
            session_id=session_id,
            run_id=run_id,
            plan=result.original_plan,
            provider=provider,
            approval_ids=approval_ids,
        )
        for action in result.original_plan.actions:
            session.statuses[action.action_id] = "pending" if action.action_id in approval_ids else "ready"
        self._sessions[session_id] = session
        return self._result(self._session_dict(session))

    @classmethod
    def _session_dict(cls, session: BootstrapSession) -> dict[str, Any]:
        actions = []
        for action in session.plan.actions:
            approval_id = session.approval_ids.get(action.action_id)
            request = session.provider.get_request(approval_id) if approval_id else None
            actions.append(
                {
                    "action_id": action.action_id,
                    "description": action.description,
                    "priority": action.priority,
                    "context": action.context,
                    "status": session.statuses.get(action.action_id, "pending"),
                    "approval_id": approval_id,
                    "risk_level": request.risk_level if request else None,
                }
            )
        return {
            "session_id": session.session_id,
            "run_id": session.run_id,
            "state": "completed" if actions and all(item["status"] in {"completed", "rejected"} for item in actions) else "active",
            "actions": actions,
            "results": session.results,
        }

    def session(self, session_id: str) -> BackendResult:
        session = self._sessions.get(session_id)
        if session is None:
            return self._result({"error": "Session not found."}, status="not_found")
        return self._result(self._session_dict(session))

    def resolve_action(self, session_id: str, action_id: str, approve: bool) -> BackendResult:
        session = self._sessions.get(session_id)
        if session is None:
            return self._result({"error": "Session not found."}, status="not_found")
        if action_id not in session.approval_ids:
            return self._result({"error": "Action is not approval-gated in this session."}, status="bad_request")
        current = session.statuses.get(action_id)
        if current not in {"pending", "ready"}:
            return self._result({"error": f"Action is already {current}."}, status="conflict")

        approval_id = session.approval_ids[action_id]
        request = session.provider.approve(approval_id) if approve else session.provider.reject(approval_id)
        if request is None:
            return self._result({"error": "Approval request not found."}, status="not_found")
        if not approve:
            session.statuses[action_id] = "rejected"
            return self._result(self._session_dict(session))

        selected = [a for a in session.plan.actions if a.action_id == action_id]
        single_plan = ExecutionPlan(
            is_actionable=True,
            actions=selected,
            summary=f"GUI approved action: {action_id}",
        )
        result = PipelineEngine().run(
            mode=ExecutionMode.REAL,
            approval_provider=session.provider,
            pending_approvals={action_id: approval_id},
            run_id=session.run_id,
            plan_override=single_plan,
        )
        payload = _pipeline_dict(result)
        session.results[action_id] = payload
        session.statuses[action_id] = "completed" if result.is_success else "failed"
        return self._result(self._session_dict(session), status="ok" if result.is_success else "failed")
