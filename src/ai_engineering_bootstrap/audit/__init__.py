"""Audit module public API."""

from pathlib import Path

from ai_engineering_bootstrap.audit.dependencies import (
    DependencyDiscovery,
    ProjectDependencyProbe,
)
from ai_engineering_bootstrap.audit.evidence import (
    EvidenceEvent,
    ExecutionAuditService,
    RunEvidence,
)
from ai_engineering_bootstrap.audit.models import (
    AuditCheck,
    AuditReport,
    EnvironmentReadiness,
)
from ai_engineering_bootstrap.audit.service import AuditService
from ai_engineering_bootstrap.probes.doctor import (
    DockerExecutableProbe,
    EditableInstallProbe,
    GitExecutableProbe,
    OSProbe,
    PlatformProbe,
    PythonVersionProbe,
    RuntimeTargetProbe,
    VirtualEnvProbe,
)
from ai_engineering_bootstrap.probes.gpu import GpuProbe


def default_audit_service(project_root: Path | None = None) -> AuditService:
    """Create the default audit service with standard probes."""
    root = (project_root or Path.cwd()).resolve()
    probes = [
        PythonVersionProbe(),
        VirtualEnvProbe(),
        EditableInstallProbe(),
        *[ProjectDependencyProbe(req) for req in DependencyDiscovery(root).discover(include_dev=True)],
        GitExecutableProbe(),
        DockerExecutableProbe(),
        OSProbe(),
        PlatformProbe(),
        RuntimeTargetProbe(),
        GpuProbe(),
    ]
    return AuditService(probes=probes)

__all__ = ["AuditCheck", "AuditReport", "AuditService", "EnvironmentReadiness", "EvidenceEvent", "ExecutionAuditService", "RunEvidence", "default_audit_service"]
