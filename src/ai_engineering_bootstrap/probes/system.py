"""Read-only probes for operating-system and Python information."""

from __future__ import annotations

import platform
import sys
from collections.abc import Callable

from ai_engineering_bootstrap.models import AuditCheck, AuditStatus


class OperatingSystemProbe:
    """Report operating-system facts from the Python standard library."""

    def __init__(
        self,
        system: Callable[[], str] = platform.system,
        release: Callable[[], str] = platform.release,
        machine: Callable[[], str] = platform.machine,
    ) -> None:
        self._system = system
        self._release = release
        self._machine = machine

    def run(self) -> AuditCheck:
        """Return normalized operating-system information."""
        try:
            return AuditCheck(
                name="operating_system",
                status=AuditStatus.AVAILABLE,
                facts={
                    "name": self._system() or "unknown",
                    "release": self._release() or "unknown",
                    "architecture": self._machine() or "unknown",
                },
            )
        # except Exception as error:  # Defensive boundary around platform APIs.
        except BaseException as error:  # Defensive boundary around platform APIs.
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise

            return AuditCheck(
                name="operating_system",
                status=AuditStatus.ERROR,
                diagnostic=str(error),
            )


class PythonVersionProbe:
    """Report facts about the running Python interpreter."""

    def run(self) -> AuditCheck:
        """Return the active Python version and executable path."""
        version = sys.version_info
        return AuditCheck(
            name="python",
            status=AuditStatus.AVAILABLE,
            facts={
                "version": f"{version.major}.{version.minor}.{version.micro}",
                "executable": sys.executable,
                "implementation": platform.python_implementation(),
            },
        )
