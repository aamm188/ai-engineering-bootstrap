"""Read-only probes for Python environment and package availability."""

from __future__ import annotations

import importlib.metadata
import logging
import sys

from ai_engineering_bootstrap.models import AuditCheck, AuditStatus

logger = logging.getLogger(__name__)


class VirtualEnvironmentProbe:
    """Check if running inside a virtual environment."""

    def run(self) -> AuditCheck:
        """Return whether the interpreter is running in a virtual environment."""
        # Check using multiple methods for cross-platform reliability
        in_venv = (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix) or (
            hasattr(sys, "real_prefix") and sys.real_prefix != sys.prefix
        )

        if in_venv:
            return AuditCheck(
                name="virtual_environment",
                status=AuditStatus.AVAILABLE,
                facts={"path": sys.prefix},
            )
        return AuditCheck(
            name="virtual_environment",
            status=AuditStatus.NOT_FOUND,
            diagnostic="Not running inside a virtual environment",
        )


class EditableInstallProbe:
    """Check if this package is installed in editable mode."""

    def run(self) -> AuditCheck:
        """Return whether ai-engineering-bootstrap is installed as editable."""
        try:
            dist = importlib.metadata.distribution("ai-engineering-bootstrap")
            # Check if it's an editable install by looking at direct_url.json
            direct_url = dist.read_text("direct_url.json")
            if direct_url is not None:
                return AuditCheck(
                    name="editable_install",
                    status=AuditStatus.AVAILABLE,
                    facts={"package": "ai-engineering-bootstrap"},
                )
        except importlib.metadata.PackageNotFoundError:
            pass
        except Exception as error:
            logger.debug("Unexpected error checking editable install", exc_info=error)

        return AuditCheck(
            name="editable_install",
            status=AuditStatus.NOT_FOUND,
            diagnostic="Package not installed in editable mode",
        )


class PythonPackageProbe:
    """Check if a required Python package is installed."""

    def __init__(self, package_name: str) -> None:
        self._package_name = package_name

    def run(self) -> AuditCheck:
        """Return whether the package is installed with its version."""
        try:
            version = importlib.metadata.version(self._package_name)
            return AuditCheck(
                name=self._package_name.lower(),
                status=AuditStatus.AVAILABLE,
                facts={"version": version},
            )
        except importlib.metadata.PackageNotFoundError:
            return AuditCheck(
                name=self._package_name.lower(),
                status=AuditStatus.NOT_FOUND,
                diagnostic=f"Package '{self._package_name}' is not installed",
            )
        except Exception as error:  # noqa: BLE001
            return AuditCheck(
                name=self._package_name.lower(),
                status=AuditStatus.ERROR,
                diagnostic=str(error),
            )
