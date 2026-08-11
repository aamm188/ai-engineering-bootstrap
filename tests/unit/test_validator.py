"""Unit tests for the ExecutionPlan Validator."""

from ai_engineering_bootstrap.executor.validator import ExecutionPlanValidator
from ai_engineering_bootstrap.planner.models import ExecutionPlan, ExecutionPlanAction


def _make_plan(actions: list[ExecutionPlanAction]) -> ExecutionPlan:
    return ExecutionPlan(is_actionable=len(actions) > 0, actions=actions, summary="Test")

def test_validate_empty_plan() -> None:
    """Empty plan should be valid."""
    plan = _make_plan([])
    validator = ExecutionPlanValidator()
    result = validator.validate(plan)
    
    assert result.is_valid is True
    assert len(result.errors) == 0

def test_validate_valid_action() -> None:
    """Valid known action should pass."""
    action = ExecutionPlanAction(action_id="install_git", description="Install Git", priority=1)
    plan = _make_plan([action])
    
    validator = ExecutionPlanValidator()
    result = validator.validate(plan)
    
    assert result.is_valid is True
    assert len(result.errors) == 0

def test_validate_empty_action_id_fails() -> None:
    """Action with empty ID should fail validation."""
    action = ExecutionPlanAction(action_id="", description="Bad Action", priority=1)
    plan = _make_plan([action])
    
    validator = ExecutionPlanValidator()
    result = validator.validate(plan)
    
    assert result.is_valid is False
    assert any("empty" in err.lower() for err in result.errors)

def test_validate_duplicate_actions_fails() -> None:
    """Duplicate action IDs should fail validation."""
    actions = [
        ExecutionPlanAction(action_id="install_git", description="Git 1", priority=1),
        ExecutionPlanAction(action_id="install_git", description="Git 2", priority=2),
    ]
    plan = _make_plan(actions)
    
    validator = ExecutionPlanValidator()
    result = validator.validate(plan)
    
    assert result.is_valid is False
    assert any("duplicate" in err.lower() for err in result.errors)


def test_validate_same_action_id_with_different_packages_is_valid() -> None:
    """Same handler action may target different packages in one plan."""
    actions = [
        ExecutionPlanAction(
            action_id="install_python_package",
            description="Install colorama",
            priority=1,
            context={"package": "colorama"},
        ),
        ExecutionPlanAction(
            action_id="install_python_package",
            description="Install requests",
            priority=1,
            context={"package": "requests"},
        ),
    ]
    plan = _make_plan(actions)

    result = ExecutionPlanValidator().validate(plan)

    assert result.is_valid is True
    assert result.errors == []


def test_validate_same_action_and_package_fails() -> None:
    """An identical action target must still be rejected as a duplicate."""
    actions = [
        ExecutionPlanAction(
            action_id="install_python_package",
            description="Install requests",
            priority=1,
            context={"package": "requests"},
        ),
        ExecutionPlanAction(
            action_id="install_python_package",
            description="Install requests again",
            priority=2,
            context={"package": "requests"},
        ),
    ]
    plan = _make_plan(actions)

    result = ExecutionPlanValidator().validate(plan)

    assert result.is_valid is False
    assert any("duplicate" in err.lower() for err in result.errors)

def test_validate_missing_description_warning() -> None:
    """Missing description should trigger warning, not error."""
    action = ExecutionPlanAction(action_id="install_git", description="", priority=1)
    plan = _make_plan([action])
    
    validator = ExecutionPlanValidator()
    result = validator.validate(plan)
    
    assert result.is_valid is True # Still valid
    assert len(result.warnings) > 0
    assert any("description" in w.lower() for w in result.warnings)

def test_validate_deterministic_order() -> None:
    """Validation result should be deterministic."""
    actions = [
        ExecutionPlanAction(action_id=f"action_{i}", description=f"Desc {i}", priority=i)
        for i in range(3)
    ]
    plan = _make_plan(actions)
    validator = ExecutionPlanValidator()
    
    res1 = validator.validate(plan)
    res2 = validator.validate(plan)
    
    assert res1.errors == res2.errors
    assert res1.warnings == res2.warnings
    assert res1.is_valid == res2.is_valid
