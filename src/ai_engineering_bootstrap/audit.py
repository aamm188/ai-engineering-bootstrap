"""Application service for aggregating environment audit probes."""

from __future__ import annotations

from collections.abc import Iterable

from ai_engineering_bootstrap.models import (
    AuditCheck,
    AuditProbe,
    AuditReport,
    AuditStatus,
)
from ai_engineering_bootstrap.probes.environment import (
    EditableInstallProbe,
    PythonPackageProbe,
    VirtualEnvironmentProbe,
)
from ai_engineering_bootstrap.probes.executables import docker_probe, git_probe
from ai_engineering_bootstrap.probes.gpu import GpuProbe
from ai_engineering_bootstrap.probes.system import (
    OperatingSystemProbe,
    PythonVersionProbe,
)


class AuditService:
    """Run independent probes while isolating unexpected probe failures."""

    def __init__(self, probes: Iterable[AuditProbe]) -> None:
        self._probes = tuple(probes)

    def run(self) -> AuditReport:
        """Run every configured probe and return a complete ordered report."""
        checks: list[AuditCheck] = []
        for probe in self._probes:
            try:
                checks.append(probe.run())
            except BaseException as error:  # Preserve the aggregate report while allowing interruption signals.
                if isinstance(error, (KeyboardInterrupt, SystemExit)):
                    raise
                checks.append(
                    AuditCheck(
                        name=type(probe).__name__,
                        status=AuditStatus.ERROR,
                        diagnostic=str(error),
                    )
                )
        return AuditReport(checks=tuple(checks))


def default_audit_service() -> AuditService:
    """Build the application service with all Phase 1 audit probes."""
    return AuditService(
        (
            OperatingSystemProbe(),
            PythonVersionProbe(),
            git_probe(),
            docker_probe(),
            GpuProbe(),
        )
    )


def doctor_audit_service() -> AuditService:
    """Build the audit service for the Environment Doctor feature."""
    return AuditService(
        (
            PythonVersionProbe(),
            VirtualEnvironmentProbe(),
            EditableInstallProbe(),
            PythonPackageProbe("typer"),
            PythonPackageProbe("rich"),
            PythonPackageProbe("pytest"),
            PythonPackageProbe("ruff"),
            git_probe(),
            docker_probe(),
            OperatingSystemProbe(),
        )
    )
