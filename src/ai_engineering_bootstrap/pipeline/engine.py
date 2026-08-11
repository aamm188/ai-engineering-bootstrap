#!/usr/bin/env python3
"""Pipeline engine for audit, planning, approval, execution, verification and recovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ai_engineering_bootstrap.agent.models import AgentDecision
from ai_engineering_bootstrap.agent.planning import AgentPlanningService
from ai_engineering_bootstrap.agent.runtime import AgentRuntime
from ai_engineering_bootstrap.approval.models import ApprovalRequest, ApprovalStatus
from ai_engineering_bootstrap.approval.provider import ApprovalProvider
from ai_engineering_bootstrap.audit import ExecutionAuditService, default_audit_service
from ai_engineering_bootstrap.audit.models import AuditReport
from ai_engineering_bootstrap.executor import ExecutionResult, ExecutorEngine
from ai_engineering_bootstrap.executor.mode import ExecutionMode
from ai_engineering_bootstrap.executor.policy import SafetyGate
from ai_engineering_bootstrap.executor.recovery import (
    FailureRecord,
    FailureType,
    RetryPolicy,
)
from ai_engineering_bootstrap.executor.validator import (
    ExecutionPlanValidator,
    ValidationResult,
)
from ai_engineering_bootstrap.planner import PlannerEngine
from ai_engineering_bootstrap.planner.models import ExecutionPlan


@dataclass(frozen=True)
class PipelineResult:
    """Complete observable result of one pipeline run."""

    audit_report: AuditReport
    original_plan: ExecutionPlan
    validation_result: ValidationResult
    execution_result: ExecutionResult | None
    verification_result: Any | None
    replan_requested: bool = False
    replanned_plan: ExecutionPlan | None = None
    failure_records: list[FailureRecord] = field(default_factory=list)
    agent_decision: AgentDecision | None = None
    approval_requests: list[ApprovalRequest] = field(default_factory=list)
    is_pending_approval: bool = False
    is_rejected_approval: bool = False
    run_evidence: Any | None = None
    replan_count: int = 0
    execution_history: list[ExecutionResult] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        """Return true only when validation, approval, execution and verification succeed."""
        if self.execution_result is None or not self.validation_result.is_valid:
            return False
        if self.is_pending_approval or self.is_rejected_approval:
            return False
        if not self.execution_result.is_success:
            return False
        if self.verification_result:
            results = self.verification_result
            if any(getattr(item, "status", None).value == "failed" for item in results):
                return False
        return True


class PipelineEngine:
    """Coordinate the backend pipeline with bounded recovery and evidence."""

    def _approval_gate(
        self,
        plan: ExecutionPlan,
        approval_provider: ApprovalProvider | None,
        pending_approvals: dict[str, str | list[str]] | None,
        run_id: str,
    ) -> tuple[list[ApprovalRequest], list[ApprovalRequest], set[int]]:
        """Return pending/rejected approvals; never execute while either exists."""
        if approval_provider is None:
            return [], [], set()

        safety_gate = SafetyGate()
        pending: list[ApprovalRequest] = []
        rejected: list[ApprovalRequest] = []
        rejected_action_indexes: set[int] = set()
        plan_id_value = getattr(plan, "plan_id", None)
        if not isinstance(plan_id_value, str):
            plan_id_value = getattr(plan, "id", "")
        plan_id = str(plan_id_value)

        approval_offsets: dict[str, int] = {}

        for action_index, action in enumerate(plan.actions):
            action_id_value = getattr(action, "action_id", None)
            if not isinstance(action_id_value, str):
                action_id_value = getattr(action, "id", "")
            action_id = str(action_id_value)
            policy = getattr(action, "policy", None)
            requirement = getattr(getattr(policy, "approval_requirement", None), "name", None)
            requires_approval = safety_gate.requires_human_approval(action_id)
            explicit_approval = getattr(action, "requires_approval", None)
            if requirement == "REQUIRED":
                requires_approval = True
            elif isinstance(explicit_approval, bool):
                requires_approval = explicit_approval
            if not requires_approval:
                continue

            approval_id = None
            if pending_approvals:
                configured = pending_approvals.get(action_id)
                if isinstance(configured, list):
                    offset = approval_offsets.get(action_id, 0)
                    if offset < len(configured):
                        approval_id = configured[offset]
                        approval_offsets[action_id] = offset + 1
                elif isinstance(configured, str):
                    # Backward-compatible form for plans with a unique action ID.
                    offset = approval_offsets.get(action_id, 0)
                    if offset == 0:
                        approval_id = configured
                        approval_offsets[action_id] = 1

            request = approval_provider.get_request(approval_id) if approval_id else None
            status = approval_provider.get_status(approval_id) if approval_id else None

            if request and (
                request.action_id != action_id
                or request.plan_id != plan_id
                or request.run_id != run_id
            ):
                rejected.append(request)
                rejected_action_indexes.add(action_index)
                continue

            if status == ApprovalStatus.APPROVED:
                continue
            if status == ApprovalStatus.REJECTED:
                if request:
                    rejected.append(request)
                rejected_action_indexes.add(action_index)
                continue
            if status == ApprovalStatus.PENDING:
                if request:
                    pending.append(request)
                continue

            policy_info = safety_gate.get_policy(action_id)
            risk_level = policy_info.risk.value if policy_info else "UNKNOWN"
            action_reason = getattr(action, "reason", None)
            action_description = getattr(action, "description", None)
            reason = action_reason or action_description or "Action requires approval"

            # Approval must identify the concrete action target. Multiple plan
            # entries may share the same action_id (for example, installing
            # different Python packages), so action_id alone is not sufficient
            # for an informed human decision.
            context = getattr(action, "context", None)
            if isinstance(context, dict):
                package_name = context.get("package") or context.get("requirement")
                if package_name and action_id == "install_python_package":
                    reason = f"Install Python package: {package_name}"

            pending.append(
                approval_provider.request_approval(
                    action_id=action_id,
                    plan_id=plan_id,
                    run_id=run_id,
                    reason=reason,
                    risk_level=risk_level,
                )
            )

        return pending, rejected, rejected_action_indexes

    @staticmethod
    def _classify_failures(execution_result: ExecutionResult, policy: RetryPolicy) -> list[FailureRecord]:
        """Classify failures in deterministic result order."""
        return [
            record
            for result in execution_result.results
            if (record := policy.classify_failure(result)).failure_type != FailureType.NONE
        ]

    def run(
        self,
        mode: ExecutionMode = ExecutionMode.SAFE,
        max_retry_attempts: int = 1,
        approval_provider: ApprovalProvider | None = None,
        pending_approvals: dict[str, str | list[str]] | None = None,
        run_id: str = "default-run",
        agent_planning_service: AgentPlanningService | None = None,
        agent_context: str | None = None,
        max_replans: int = 1,
    ) -> PipelineResult:
        """Run one bounded pipeline execution and at most ``max_replans`` recovery cycles."""
        evidence = ExecutionAuditService(run_id)
        evidence.record("audit", "started")
        report = default_audit_service().run()
        evidence.record("audit", "completed", health_score=report.readiness.health_score)

        planner = PlannerEngine()
        agent_decision = None
        agent_metadata: dict[str, Any] = {}
        if agent_planning_service is not None and agent_context is not None:
            runtime_result = AgentRuntime(agent_planning_service).run(agent_context, run_id)
            agent_decision = runtime_result.planning.decision
            original_plan = runtime_result.planning.plan
            agent_metadata = AgentRuntime.metadata(runtime_result)
            evidence.record("agent", "completed", **agent_metadata)
        else:
            original_plan = planner.generate_plan(report)

        evidence.record("planning", "completed", plan_id=original_plan.plan_id)
        validator = ExecutionPlanValidator()
        validation_result = validator.validate(original_plan)
        evidence.record("validation", "passed" if validation_result.is_valid else "failed")
        if not validation_result.is_valid:
            evidence.complete("failed", reason="invalid_plan")
            return PipelineResult(
                report,
                original_plan,
                validation_result,
                None,
                None,
                agent_decision=agent_decision,
                run_evidence=evidence.snapshot(),
            )

        pending, rejected, rejected_action_indexes = self._approval_gate(
            original_plan, approval_provider, pending_approvals, run_id
        )
        if pending:
            evidence.record("approval", "pending_approval", count=len(pending))
            evidence.complete("pending_approval")
            return PipelineResult(
                report,
                original_plan,
                validation_result,
                None,
                None,
                approval_requests=pending,
                is_pending_approval=True,
                agent_decision=agent_decision,
                run_evidence=evidence.snapshot(),
            )

        if rejected:
            evidence.record(
                "approval",
                "resolved_with_rejections",
                count=len(rejected),
                rejected_action_count=len(rejected_action_indexes),
            )

        # _approval_gate has verified every approval-required action and identified
        # rejected actions that must be skipped without blocking other actions.
        executor_kwargs: dict[str, Any] = {"mode": mode}
        if rejected_action_indexes:
            executor_kwargs["rejected_action_indexes"] = rejected_action_indexes
        if mode == ExecutionMode.REAL and approval_provider is not None:
            executor_kwargs["is_approved"] = True
        executor = ExecutorEngine(**executor_kwargs)
        policy = RetryPolicy(max_attempts=max_retry_attempts)
        execution_history: list[ExecutionResult] = []
        failure_records: list[FailureRecord] = []
        current_plan = original_plan
        current_report = report
        replanned_plan: ExecutionPlan | None = None
        replan_count = 0
        replan_requested = False
        final_execution: ExecutionResult | None = None
        final_verification: Any | None = None

        while True:
            evidence.record("execution", "started", plan_id=current_plan.plan_id, replan_count=replan_count)
            execution = executor.execute(current_plan, max_attempts=max_retry_attempts)
            execution_history.append(execution)
            evidence.record("execution", "completed", success=execution.is_success)

            verification = executor.verify(current_plan, execution)
            final_execution = execution
            final_verification = verification
            verification_failed = any(item.status.value == "failed" for item in verification)
            evidence.record("verification", "failed" if verification_failed else "completed")

            failures = self._classify_failures(execution, policy)
            failure_records.extend(failures)
            needs_replan = any(record.requires_replan for record in failures) or verification_failed
            if not needs_replan:
                evidence.complete("completed")
                break

            replan_requested = True
            if replan_count >= max(0, max_replans):
                evidence.record("recovery", "stopped", reason="replan_limit_reached")
                evidence.complete("failed", reason="replan_limit_reached")
                break

            replan_count += 1
            evidence.record("recovery", "replan_requested", replan_count=replan_count)
            current_report = default_audit_service().run()
            evidence.record("audit", "completed_after_failure", health_score=current_report.readiness.health_score)
            candidate = planner.generate_plan(current_report)
            candidate_validation = validator.validate(candidate)
            evidence.record("replan_validation", "passed" if candidate_validation.is_valid else "failed")
            if not candidate_validation.is_valid:
                evidence.complete("failed", reason="invalid_replanned_plan")
                break

            pending, rejected, rejected_action_indexes = self._approval_gate(
                candidate, approval_provider, pending_approvals, run_id
            )
            if pending:
                evidence.record("approval", "blocked_replan", count=len(pending))
                evidence.complete("pending_approval")
                return PipelineResult(
                    current_report,
                    original_plan,
                    validation_result,
                    final_execution,
                    final_verification,
                    replan_requested=True,
                    replanned_plan=candidate,
                    failure_records=failure_records,
                    agent_decision=agent_decision,
                    approval_requests=pending,
                    is_pending_approval=True,
                    run_evidence=evidence.snapshot(),
                    replan_count=replan_count,
                    execution_history=execution_history,
                )

            if rejected:
                evidence.record(
                    "approval",
                    "replanned_with_rejections",
                    count=len(rejected),
                    rejected_action_count=len(rejected_action_indexes),
                )

            replanned_plan = candidate
            current_plan = candidate
            executor_kwargs = {"mode": mode}
            if rejected_action_indexes:
                executor_kwargs["rejected_action_indexes"] = rejected_action_indexes
            if mode == ExecutionMode.REAL and approval_provider is not None:
                executor_kwargs["is_approved"] = True
            executor = ExecutorEngine(**executor_kwargs)
            evidence.record("recovery", "replanned", plan_id=current_plan.plan_id)

        return PipelineResult(
            current_report,
            original_plan,
            validation_result,
            final_execution,
            final_verification,
            replan_requested=replan_requested,
            replanned_plan=replanned_plan,
            failure_records=failure_records,
            agent_decision=agent_decision,
            run_evidence=evidence.snapshot(),
            replan_count=replan_count,
            execution_history=execution_history,
        )


__all__ = ["PipelineEngine", "PipelineResult"]
