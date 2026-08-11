"""Bounded Agent runtime/session boundary."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any

from ai_engineering_bootstrap.agent.planning import (
    AgentPlanningResult,
    AgentPlanningService,
)


class AgentSessionStatus(str, Enum):
    """Lifecycle state of an Agent planning session."""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class AgentSession:
    """Immutable identity and lifecycle state for one Agent interaction."""

    session_id: str
    run_id: str
    status: AgentSessionStatus


@dataclass(frozen=True)
class AgentRuntimeResult:
    """Result of a bounded Agent session."""

    session: AgentSession
    planning: AgentPlanningResult


class AgentRuntime:
    """Own Agent session lifecycle without any execution capability."""

    def __init__(self, planning_service: AgentPlanningService) -> None:
        self._planning_service = planning_service

    def run(self, context: str, run_id: str) -> AgentRuntimeResult:
        """Create one session, perform one decision/plan operation, then close it."""
        session_id = f"agent-{uuid.uuid4()}"
        try:
            planning = self._planning_service.decide_and_plan(context)
        except Exception:
            # The immutable failed state is intentionally created before re-raising.
            AgentSession(session_id, run_id, AgentSessionStatus.FAILED)
            raise

        completed = AgentSession(session_id, run_id, AgentSessionStatus.COMPLETED)
        return AgentRuntimeResult(session=completed, planning=planning)

    @staticmethod
    def metadata(result: AgentRuntimeResult) -> dict[str, Any]:
        """Expose session identity without exposing provider internals."""
        return {
            "session_id": result.session.session_id,
            "run_id": result.session.run_id,
            "status": result.session.status.value,
            "decision_id": result.planning.decision.decision_id,
        }


__all__ = ["AgentRuntime", "AgentRuntimeResult", "AgentSession", "AgentSessionStatus"]
