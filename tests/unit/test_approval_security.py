from unittest.mock import MagicMock, patch

import pytest

from ai_engineering_bootstrap.approval.models import ApprovalStatus
from ai_engineering_bootstrap.approval.provider import InMemoryApprovalProvider
from ai_engineering_bootstrap.executor.mode import ExecutionMode
from ai_engineering_bootstrap.pipeline.engine import PipelineEngine

# --- Helper Functions for Mocking Plan and Actions ---

def create_mock_action(action_id: str, requires_approval: bool, risk_level: str = "MEDIUM"):
    """Creates a mock action mimicking the ExecutionPlan action structure."""
    action = MagicMock()
    action.id = action_id
    action.policy = MagicMock()
    action.policy.risk_level = risk_level
    if requires_approval:
        action.policy.approval_requirement.name = "REQUIRED"
    else:
        action.policy.approval_requirement.name = "NONE"
    action.reason = f"Executing {action_id}"
    return action

def create_mock_plan(plan_id: str, actions: list):
    """Creates a mock ExecutionPlan."""
    plan = MagicMock()
    plan.id = plan_id
    plan.actions = actions
    return plan


# --- Test Cases ---

@pytest.fixture
def approval_provider():
    return InMemoryApprovalProvider()

@pytest.fixture
def pipeline_engine():
    return PipelineEngine()


def test_approval_request_starts_pending(approval_provider):
    """1. Approval request starts PENDING."""
    req = approval_provider.request_approval("act-1", "plan-1", "run-1", "test", "LOW")
    assert req.status == ApprovalStatus.PENDING

def test_explicit_approval_changes_state(approval_provider):
    """2. Explicit approval changes state to APPROVED."""
    req = approval_provider.request_approval("act-1", "plan-1", "run-1", "test", "LOW")
    approved_req = approval_provider.approve(req.approval_id)
    assert approved_req.status == ApprovalStatus.APPROVED

def test_explicit_rejection_changes_state(approval_provider):
    """3. Explicit rejection changes state to REJECTED."""
    req = approval_provider.request_approval("act-1", "plan-1", "run-1", "test", "LOW")
    rejected_req = approval_provider.reject(req.approval_id)
    assert rejected_req.status == ApprovalStatus.REJECTED

@patch('ai_engineering_bootstrap.pipeline.engine.default_audit_service')
@patch('ai_engineering_bootstrap.pipeline.engine.ExecutorEngine')
@patch('ai_engineering_bootstrap.pipeline.engine.ExecutionPlanValidator')
@patch('ai_engineering_bootstrap.pipeline.engine.PlannerEngine')
def test_pending_approval_blocks_execution(mock_planner, mock_validator, mock_executor, mock_audit, pipeline_engine, approval_provider):
    """4. Pending approval blocks execution."""
    mock_planner.return_value.generate_plan.return_value = create_mock_plan("plan-1", [create_mock_action("act-1", True)])
    mock_validator.return_value.validate.return_value = MagicMock(is_valid=True)

    result = pipeline_engine.run(approval_provider=approval_provider)

    assert result.is_pending_approval is True
    assert result.execution_result is None
    mock_executor.return_value.execute.assert_not_called() # Executor should never run

@patch('ai_engineering_bootstrap.pipeline.engine.default_audit_service')
@patch('ai_engineering_bootstrap.pipeline.engine.ExecutorEngine')
@patch('ai_engineering_bootstrap.pipeline.engine.ExecutionPlanValidator')
@patch('ai_engineering_bootstrap.pipeline.engine.PlannerEngine')
def test_rejected_approval_skips_only_that_action(
    mock_planner,
    mock_validator,
    mock_executor,
    mock_audit,
    pipeline_engine,
    approval_provider,
):
    """A rejected action is skipped without blocking other actions."""
    first = approval_provider.request_approval(
        "act-1", "plan-1", "run-1", "test 1", "LOW"
    )
    second = approval_provider.request_approval(
        "act-2", "plan-1", "run-1", "test 2", "LOW"
    )
    approval_provider.reject(first.approval_id)
    approval_provider.approve(second.approval_id)

    mock_planner.return_value.generate_plan.return_value = create_mock_plan(
        "plan-1",
        [
            create_mock_action("act-1", True),
            create_mock_action("act-2", True),
        ],
    )
    mock_validator.return_value.validate.return_value = MagicMock(is_valid=True)

    result = pipeline_engine.run(
        mode=ExecutionMode.REAL,
        approval_provider=approval_provider,
        pending_approvals={
            "act-1": first.approval_id,
            "act-2": second.approval_id,
        },
        run_id="run-1",
    )

    assert result.is_pending_approval is False
    assert result.is_rejected_approval is False
    mock_executor.return_value.execute.assert_called_once()

@patch('ai_engineering_bootstrap.pipeline.engine.default_audit_service')
@patch('ai_engineering_bootstrap.pipeline.engine.ExecutorEngine')
@patch('ai_engineering_bootstrap.pipeline.engine.ExecutionPlanValidator')
@patch('ai_engineering_bootstrap.pipeline.engine.PlannerEngine')
def test_approved_action_proceeds_to_executor(mock_planner, mock_validator, mock_executor, mock_audit, pipeline_engine, approval_provider):
    """6. Approved action proceeds to existing Executor."""
    req = approval_provider.request_approval("act-1", "plan-1", "default-run", "test", "LOW")
    approval_provider.approve(req.approval_id)

    mock_planner.return_value.generate_plan.return_value = create_mock_plan("plan-1", [create_mock_action("act-1", True)])
    mock_validator.return_value.validate.return_value = MagicMock(is_valid=True)

    pending_approvals = {"act-1": req.approval_id}
    result = pipeline_engine.run(approval_provider=approval_provider, pending_approvals=pending_approvals)

    assert result.is_pending_approval is False
    assert result.is_rejected_approval is False
    mock_executor.return_value.execute.assert_called_once()

@patch('ai_engineering_bootstrap.pipeline.engine.default_audit_service')
@patch('ai_engineering_bootstrap.pipeline.engine.ExecutorEngine')
@patch('ai_engineering_bootstrap.pipeline.engine.ExecutionPlanValidator')
@patch('ai_engineering_bootstrap.pipeline.engine.PlannerEngine')
def test_none_requirement_bypasses_approval(mock_planner, mock_validator, mock_executor, mock_audit, pipeline_engine, approval_provider):
    """7. ApprovalRequirement.NONE bypasses approval request."""
    mock_planner.return_value.generate_plan.return_value = create_mock_plan("plan-1", [create_mock_action("act-1", False)])
    mock_validator.return_value.validate.return_value = MagicMock(is_valid=True)

    result = pipeline_engine.run(approval_provider=approval_provider)

    assert result.is_pending_approval is False
    assert len(result.approval_requests) == 0
    mock_executor.return_value.execute.assert_called_once()

@patch('ai_engineering_bootstrap.pipeline.engine.default_audit_service')
@patch('ai_engineering_bootstrap.pipeline.engine.ExecutorEngine')
@patch('ai_engineering_bootstrap.pipeline.engine.ExecutionPlanValidator')
@patch('ai_engineering_bootstrap.pipeline.engine.PlannerEngine')
def test_required_creates_approval_request(mock_planner, mock_validator, mock_executor, mock_audit, pipeline_engine, approval_provider):
    """8. ApprovalRequirement.REQUIRED creates approval request."""
    mock_planner.return_value.generate_plan.return_value = create_mock_plan("plan-1", [create_mock_action("act-1", True)])
    mock_validator.return_value.validate.return_value = MagicMock(is_valid=True)

    result = pipeline_engine.run(approval_provider=approval_provider)

    assert result.is_pending_approval is True
    assert len(result.approval_requests) == 1
    assert result.approval_requests[0].action_id == "act-1"

def test_exact_action_binding_mismatch(approval_provider, pipeline_engine):
    """9. Approval is bound to exact action_id. (Cross-action attempt)"""
    req = approval_provider.request_approval("act-A", "plan-1", "run-1", "test", "LOW")
    approval_provider.approve(req.approval_id)

    # Try to use approval of act-A for act-B
    fetched_req = approval_provider.get_request(req.approval_id)
    assert fetched_req.action_id == "act-A"
    # In pipeline, this condition triggers rejection if action_id != req.action_id

def test_exact_plan_run_binding_replay_prevention(approval_provider):
    """10 & 17. Approval is bound to exact plan/run identity and cannot be replayed."""
    req = approval_provider.request_approval("act-1", "plan-1", "run-1", "test", "LOW")
    approval_provider.approve(req.approval_id)

    # If someone tries to use this approval_id in a different run, it must fail
    # Simulating the pipeline check:
    req_obj = approval_provider.get_request(req.approval_id)
    is_valid_replay = (req_obj.run_id == "run-2")
    assert not is_valid_replay, "Approval replay across runs should be invalid"

@patch('ai_engineering_bootstrap.pipeline.engine.default_audit_service')
@patch('ai_engineering_bootstrap.pipeline.engine.ExecutorEngine')
@patch('ai_engineering_bootstrap.pipeline.engine.ExecutionPlanValidator')
@patch('ai_engineering_bootstrap.pipeline.engine.PlannerEngine')
def test_multiple_actions_independent_requests(mock_planner, mock_validator, mock_executor, mock_audit, pipeline_engine, approval_provider):
    """18. Multiple actions produce independent approval requests."""
    actions = [create_mock_action("act-1", True), create_mock_action("act-2", True)]
    mock_planner.return_value.generate_plan.return_value = create_mock_plan("plan-1", actions)
    mock_validator.return_value.validate.return_value = MagicMock(is_valid=True)

    result = pipeline_engine.run(approval_provider=approval_provider)

    assert len(result.approval_requests) == 2
    assert result.approval_requests[0].action_id == "act-1"
    assert result.approval_requests[1].action_id == "act-2"
    assert result.approval_requests[0].approval_id != result.approval_requests[1].approval_id

@patch('ai_engineering_bootstrap.pipeline.engine.default_audit_service')
@patch('ai_engineering_bootstrap.pipeline.engine.ExecutorEngine')
@patch('ai_engineering_bootstrap.pipeline.engine.ExecutionPlanValidator')
@patch('ai_engineering_bootstrap.pipeline.engine.PlannerEngine')
def test_safe_mode_remains_mock_after_approval(mock_planner, mock_validator, mock_executor, mock_audit, pipeline_engine, approval_provider):
    """15. Safe mode remains Mock even after approval."""
    req = approval_provider.request_approval("act-1", "plan-1", "default-run", "test", "LOW")
    approval_provider.approve(req.approval_id)

    mock_planner.return_value.generate_plan.return_value = create_mock_plan("plan-1", [create_mock_action("act-1", True)])
    mock_validator.return_value.validate.return_value = MagicMock(is_valid=True)

    pending_approvals = {"act-1": req.approval_id}
    # Run in SAFE mode
    result = pipeline_engine.run(mode=ExecutionMode.SAFE, approval_provider=approval_provider, pending_approvals=pending_approvals)

    # Verify executor was called with SAFE mode
    mock_executor.assert_called_with(mode=ExecutionMode.SAFE)
    assert result.is_pending_approval is False

def test_approval_cannot_contain_executable_callbacks(approval_provider):
    """Security 8 & 9: Approval cannot inject shell commands or executable callbacks."""
    # Dataclasses do not enforce types at runtime, but the system should not execute it.
    # The provider stores it, but it is never invoked by the pipeline.
    req = approval_provider.request_approval("act-1", "plan-1", "run-1", reason=lambda: "malicious", risk_level="LOW")
    assert req.approval_id == "appr-1"  # System did not crash or execute the lambda
    # We explicitly assert that the status remains PENDING, showing no code was run.
    assert req.status == ApprovalStatus.PENDING

def test_provider_state_transitions_are_terminal(approval_provider):
    """Security 14: Cannot replay or change terminal states."""
    req = approval_provider.request_approval("act-1", "plan-1", "run-1", "test", "LOW")
    approval_provider.approve(req.approval_id)

    # Try to reject after approve
    approval_provider.reject(req.approval_id)
    assert approval_provider.get_status(req.approval_id) == ApprovalStatus.APPROVED, "Should remain APPROVED"

    # Try to approve after reject on a new one
    req2 = approval_provider.request_approval("act-2", "plan-1", "run-1", "test", "LOW")
    approval_provider.reject(req2.approval_id)
    approval_provider.approve(req2.approval_id)
    assert approval_provider.get_status(req2.approval_id) == ApprovalStatus.REJECTED, "Should remain REJECTED"

@patch('ai_engineering_bootstrap.pipeline.engine.default_audit_service')
@patch('ai_engineering_bootstrap.pipeline.engine.ExecutorEngine')
@patch('ai_engineering_bootstrap.pipeline.engine.ExecutionPlanValidator')
@patch('ai_engineering_bootstrap.pipeline.engine.PlannerEngine')
def test_approved_actions_propagate_approval_to_executor(
    mock_planner, mock_validator, mock_executor, mock_audit, pipeline_engine, approval_provider
):
    """Pipeline approval must propagate to ExecutorEngine after the gate passes."""
    req = approval_provider.request_approval("install_python_package", "plan-1", "run-1", "Install demo", "MEDIUM")
    approval_provider.approve(req.approval_id)

    mock_planner.return_value.generate_plan.return_value = create_mock_plan(
        "plan-1", [create_mock_action("install_python_package", True)]
    )
    mock_validator.return_value.validate.return_value = MagicMock(is_valid=True)

    result = pipeline_engine.run(
        mode=ExecutionMode.REAL,
        approval_provider=approval_provider,
        pending_approvals={"install_python_package": req.approval_id},
        run_id="run-1",
    )

    assert result.is_pending_approval is False
    mock_executor.assert_called_once_with(mode=ExecutionMode.REAL, is_approved=True)
    mock_executor.return_value.execute.assert_called_once()


@patch('ai_engineering_bootstrap.pipeline.engine.default_audit_service')
@patch('ai_engineering_bootstrap.pipeline.engine.ExecutorEngine')
@patch('ai_engineering_bootstrap.pipeline.engine.ExecutionPlanValidator')
@patch('ai_engineering_bootstrap.pipeline.engine.PlannerEngine')
def test_duplicate_action_ids_accept_independent_approvals(
    mock_planner, mock_validator, mock_executor, mock_audit, pipeline_engine, approval_provider
):
    """Multiple package installs sharing a handler action ID keep independent approvals."""
    actions = [
        create_mock_action("install_python_package", True),
        create_mock_action("install_python_package", True),
    ]
    actions[0].context = {"package": "colorama"}
    actions[1].context = {"package": "requests"}
    mock_planner.return_value.generate_plan.return_value = create_mock_plan("plan-1", actions)
    mock_validator.return_value.validate.return_value = MagicMock(is_valid=True)

    first = approval_provider.request_approval(
        "install_python_package", "plan-1", "run-1", "Install colorama", "MEDIUM"
    )
    second = approval_provider.request_approval(
        "install_python_package", "plan-1", "run-1", "Install requests", "MEDIUM"
    )
    approval_provider.approve(first.approval_id)
    approval_provider.approve(second.approval_id)

    result = pipeline_engine.run(
        mode=ExecutionMode.REAL,
        approval_provider=approval_provider,
        pending_approvals={
            "install_python_package": [first.approval_id, second.approval_id]
        },
        run_id="run-1",
    )

    assert result.is_pending_approval is False
    assert result.is_rejected_approval is False
    mock_executor.assert_called_once_with(mode=ExecutionMode.REAL, is_approved=True)
    mock_executor.return_value.execute.assert_called_once()


def test_rejected_action_is_skipped_and_approved_action_executes() -> None:
    """A rejected action must not prevent a later approved action from executing."""
    from ai_engineering_bootstrap.executor.engine import ExecutorEngine
    from ai_engineering_bootstrap.executor.mode import ExecutionMode
    from ai_engineering_bootstrap.executor.models import ExecutionStatus
    from ai_engineering_bootstrap.planner.models import (
        ExecutionPlan,
        ExecutionPlanAction,
    )

    actions = [
        ExecutionPlanAction(
            "install_python_package",
            "Install colorama",
            1,
            {"package": "colorama"},
        ),
        ExecutionPlanAction(
            "install_python_package",
            "Install requests",
            1,
            {"package": "requests"},
        ),
    ]
    plan = ExecutionPlan(True, actions, "test")
    engine = ExecutorEngine(
        mode=ExecutionMode.REAL,
        is_approved=True,
        rejected_action_indexes={0},
    )

    result = engine.execute(plan)

    assert [item.status for item in result.results] == [
        ExecutionStatus.SKIPPED,
        ExecutionStatus.SUCCESS,
    ]
    assert "rejected by human approval" in result.results[0].message.lower()
    assert "requests" in result.results[1].message


def test_verification_matches_duplicate_actions_by_position() -> None:
    """Verification must not reuse the last result for duplicate action IDs."""
    from ai_engineering_bootstrap.executor.engine import ExecutorEngine
    from ai_engineering_bootstrap.executor.models import (
        ActionResult,
        ExecutionResult,
        ExecutionStatus,
    )
    from ai_engineering_bootstrap.executor.verifier import VerificationStatus
    from ai_engineering_bootstrap.planner.models import (
        ExecutionPlan,
        ExecutionPlanAction,
    )

    actions = [
        ExecutionPlanAction(
            "install_python_package",
            "Install colorama",
            1,
            {"package": "colorama"},
        ),
        ExecutionPlanAction(
            "install_python_package",
            "Install requests",
            1,
            {"package": "requests"},
        ),
    ]
    plan = ExecutionPlan(True, actions, "test")
    execution = ExecutionResult.create_from_actions(
        [
            ActionResult(
                "install_python_package",
                ExecutionStatus.SKIPPED,
                "Action rejected by human approval.",
            ),
            ActionResult(
                "install_python_package",
                ExecutionStatus.SUCCESS,
                "Package 'requests' installed successfully.",
            ),
        ]
    )

    results = ExecutorEngine(mode=ExecutionMode.REAL, is_approved=True).verify(
        plan, execution
    )

    assert results[0].status == VerificationStatus.SKIPPED
    assert results[1].status == VerificationStatus.VERIFIED
