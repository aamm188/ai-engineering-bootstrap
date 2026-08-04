"""Unit tests for external executable availability probes."""

import subprocess

from ai_engineering_bootstrap.models import AuditStatus
from ai_engineering_bootstrap.probes.executables import ExecutableProbe


def test_executable_probe_reports_version_without_shell() -> None:
    calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

    def runner(
        command: tuple[str, ...], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "tool version 1.2\n", "")

    check = ExecutableProbe("tool", ("tool", "--version"), runner=runner).run()

    assert check.status is AuditStatus.AVAILABLE
    assert check.facts == {"version": "tool version 1.2"}
    assert calls[0][0] == ("tool", "--version")
    assert calls[0][1]["shell"] is False


def test_executable_probe_reports_missing_executable() -> None:
    def runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError

    check = ExecutableProbe("tool", ("tool", "--version"), runner=runner).run()

    assert check.status is AuditStatus.NOT_FOUND


def test_executable_probe_reports_timeout() -> None:
    def runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="tool", timeout=5)

    check = ExecutableProbe("tool", ("tool", "--version"), runner=runner).run()

    assert check.status is AuditStatus.ERROR
    assert check.diagnostic == "version check timed out"


def test_executable_probe_reports_nonzero_exit() -> None:
    def runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 1, "", "not ready")

    check = ExecutableProbe("tool", ("tool", "--version"), runner=runner).run()

    assert check.status is AuditStatus.ERROR
    assert check.diagnostic == "not ready"


def test_executable_probe_rejects_empty_version_output() -> None:
    def runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, "", "")

    check = ExecutableProbe("tool", ("tool", "--version"), runner=runner).run()

    assert check.status is AuditStatus.ERROR
    assert check.diagnostic == "version command returned no output"
