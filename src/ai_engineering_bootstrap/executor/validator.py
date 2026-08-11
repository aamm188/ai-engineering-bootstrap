"""Execution Plan Validator - Safety Gate."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from ai_engineering_bootstrap.planner.models import ExecutionPlan


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating an execution plan."""
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ExecutionPlanValidator:
    """
    Validates an ExecutionPlan before it reaches the Executor.
    
    This acts as a Safety Gate to prevent invalid or unsafe plans from executing.
    It performs structural validation and allowlist checking.
    """

    # لیست سفید اکشن‌های شناخته‌شده و ایمن (استفاده از ClassVar برای رفع خطای RUF012)
    ALLOWED_ACTIONS: ClassVar[set[str]] = {
        "fix_venv",
        "fix_editable",
        "install_git",
        "install_docker",
        "upgrade_python",
        "check_python_version_real",
        "create_virtualenv",
        "install_python_package",
        "install_project_dependencies",
    }

    def validate(self, plan: ExecutionPlan) -> ValidationResult:
        """
        Validate the given execution plan.
        
        Returns ValidationResult with is_valid=True if safe to execute.
        Returns ValidationResult with is_valid=False if plan should be rejected.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # طرح خالی معتبر است
        if not plan.actions:
            return ValidationResult(is_valid=True, errors=[], warnings=[])

        seen_actions: set[tuple[str, str]] = set()

        for action in plan.actions:
            # 1. بررسی خالی نبودن action_id
            if not action.action_id or not action.action_id.strip():
                errors.append("Action ID cannot be empty.")
                continue

            # 2. بررسی تکراری نبودن
            package = str(action.context.get("package", "")).strip().lower()
            duplicate_key = (action.action_id, package)
            if duplicate_key in seen_actions:
                errors.append(
                    f"Duplicate action found: '{action.action_id}'"
                    + (f" for package '{package}'." if package else ".")
                )
            seen_actions.add(duplicate_key)

            # 3. بررسی عضویت در لیست سفید (Allowlist)
            if action.action_id not in self.ALLOWED_ACTIONS:
                errors.append(
                    f"Action ID '{action.action_id}' is not recognized/implemented "
                    "and is blocked by Safety Gate."
                )
            
            # 4. بررسی توضیحات (تولید هشدار اگر خالی باشد، اما خطا نیست)
            if not action.description or not action.description.strip():
                warnings.append(f"Action '{action.action_id}' has no description.")

        is_valid = len(errors) == 0
        return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)
