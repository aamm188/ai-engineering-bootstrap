#!/usr/bin/env python3
"""Executor Engine - Dispatches via Registry with Retry support."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ai_engineering_bootstrap.executor.handlers.base import ExecutionContext
from ai_engineering_bootstrap.executor.mode import ExecutionMode
from ai_engineering_bootstrap.executor.models import (
    ActionResult,
    ExecutionResult,
    ExecutionStatus,
)
from ai_engineering_bootstrap.executor.policy import SafetyGate
from ai_engineering_bootstrap.executor.recovery import RetryPolicy
from ai_engineering_bootstrap.executor.registry import ActionRegistry
from ai_engineering_bootstrap.executor.verifier import (
    VerificationResult,
    VerificationStatus,
    VerifierRegistry,
)

if TYPE_CHECKING:
    from ai_engineering_bootstrap.planner.models import ExecutionPlan


class ExecutorEngine:
    """Executes actions using handler abstraction with bounded retry."""

    def __init__(
        self,
        mode: ExecutionMode = ExecutionMode.SAFE,
        is_approved: bool = False,
        rejected_action_indexes: set[int] | None = None,
    ) -> None:
        self._mode = mode
        self._is_approved = is_approved
        self._rejected_action_indexes = rejected_action_indexes or set()
        self._registry = ActionRegistry()
        self._safety_gate = SafetyGate()
        self._verifier_registry = VerifierRegistry()

    def verify(
        self,
        plan: ExecutionPlan,
        execution_result: ExecutionResult,
    ) -> list[VerificationResult]:
        """Verify successful action results using independent read-only verifiers."""
        results: list[VerificationResult] = []
        for action_index, action in enumerate(plan.actions):
            result = (
                execution_result.results[action_index]
                if action_index < len(execution_result.results)
                else None
            )
            verifier = self._verifier_registry.get_verifier(action.action_id)
            if verifier is None:
                results.append(
                    VerificationResult(
                        action.action_id,
                        VerificationStatus.SKIPPED,
                        "No verifier registered for this action.",
                    )
                )
                continue
            if result is None:
                results.append(
                    VerificationResult(
                        action.action_id,
                        VerificationStatus.SKIPPED,
                        "No execution result exists for this action.",
                    )
                )
                continue
            context = ExecutionContext(
                mode=self._mode,
                dry_run=self._mode == ExecutionMode.SAFE,
                is_approved=self._is_approved,
            )
            results.append(verifier.verify(action, result, context))
        return results

    def execute(
        self,
        plan: ExecutionPlan,
        max_attempts: int = 1,
    ) -> ExecutionResult:
        """Process all actions deterministically with optional retry."""
        results: list[ActionResult] = []
        context = ExecutionContext(
            mode=self._mode,
            dry_run=(self._mode == ExecutionMode.SAFE),
            is_approved=self._is_approved,
        )
        policy = RetryPolicy(max_attempts=max_attempts)

        for action_index, action in enumerate(plan.actions):
            if action_index in self._rejected_action_indexes:
                results.append(
                    ActionResult(
                        action_id=action.action_id,
                        status=ExecutionStatus.SKIPPED,
                        message="Action rejected by human approval.",
                        details={"reason": "human_rejection", "action_index": action_index},
                    )
                )
                continue

            attempt = 0
            final_result: ActionResult | None = None

            while attempt < max_attempts:
                attempt += 1

                # 1. Safety Gate Check
                allowed, reason = self._safety_gate.evaluate(
                    action.action_id,
                    self._mode,
                    is_approved=self._is_approved,
                )

                if not allowed:
                    final_result = ActionResult(
                        action_id=action.action_id,
                        status=ExecutionStatus.FAILED,
                        message=f"Safety Gate Denied: {reason}",
                        details={"reason": "policy_violation"},
                    )
                    break

                # 2. Handler Lookup & Execution
                try:
                    handler = self._registry.get_handler(
                        action.action_id,
                        self._mode,
                    )
                    result = handler.execute(action, context)

                    if result.status != ExecutionStatus.FAILED:
                        final_result = result
                        break

                    failure_record = policy.classify_failure(result)
                    if not failure_record.is_retryable:
                        final_result = result
                        break

                    final_result = result

                except KeyError as err:
                    final_result = ActionResult(
                        action_id=action.action_id,
                        status=ExecutionStatus.FAILED,
                        message=str(err),
                        details={"error": "Unsupported or Unauthorized"},
                    )
                    break
                except Exception as err:  # noqa: BLE001
                    final_result = ActionResult(
                        action_id=action.action_id,
                        status=ExecutionStatus.FAILED,
                        message=f"Handler execution error: {err!s}",
                        details={},
                    )
                    rec = policy.classify_failure(final_result)
                    if not rec.is_retryable:
                        break

            if final_result:
                results.append(final_result)

        return ExecutionResult.create_from_actions(results)


__all__ = ["ExecutorEngine"]
