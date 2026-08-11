"""Execution audit evidence models and in-memory recording service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class EvidenceEvent:
    """Immutable event describing one pipeline stage or action outcome."""

    sequence: int
    stage: str
    status: str
    timestamp: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunEvidence:
    """Complete evidence envelope for one pipeline run."""

    run_id: str
    started_at: str
    completed_at: str | None
    events: tuple[EvidenceEvent, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation of the evidence."""
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "events": [
                {
                    "sequence": event.sequence,
                    "stage": event.stage,
                    "status": event.status,
                    "timestamp": event.timestamp,
                    "details": event.details,
                }
                for event in self.events
            ],
        }


class ExecutionAuditService:
    """Record structured, in-memory evidence without adding persistence dependencies."""

    def __init__(self, run_id: str) -> None:
        self._run_id = run_id
        self._started_at = _utc_now()
        self._completed_at: str | None = None
        self._events: list[EvidenceEvent] = []

    def record(self, stage: str, status: str, **details: Any) -> None:
        """Append one ordered evidence event."""
        self._events.append(
            EvidenceEvent(
                sequence=len(self._events) + 1,
                stage=stage,
                status=status,
                timestamp=_utc_now(),
                details=details,
            )
        )

    def complete(self, status: str = "completed", **details: Any) -> None:
        """Close the run and record its terminal status."""
        self.record("pipeline", status, **details)
        self._completed_at = _utc_now()

    def snapshot(self) -> RunEvidence:
        """Return an immutable evidence snapshot."""
        return RunEvidence(
            run_id=self._run_id,
            started_at=self._started_at,
            completed_at=self._completed_at,
            events=tuple(self._events),
        )


__all__ = ["EvidenceEvent", "ExecutionAuditService", "RunEvidence"]
