"""Unit tests for the Environment Doctor command."""

from typer.testing import CliRunner

from ai_engineering_bootstrap import cli
from ai_engineering_bootstrap.models import AuditCheck, AuditReport, AuditStatus

runner = CliRunner()


class StubDoctorAuditService:
    """Audit service test double with a fully healthy report."""

    def run(self) -> AuditReport:
        return AuditReport(
            checks=(
                AuditCheck(
                    name="python",
                    status=AuditStatus.AVAILABLE,
                    facts={"version": "3.12.0"},
                ),
                AuditCheck(
                    name="virtual_environment",
                    status=AuditStatus.AVAILABLE,
                    facts={"path": "/home/user/.venv"},
                ),
                AuditCheck(
                    name="editable_install",
                    status=AuditStatus.AVAILABLE,
                    facts={"package": "ai-engineering-bootstrap"},
                ),
                AuditCheck(
                    name="typer",
                    status=AuditStatus.AVAILABLE,
                    facts={"version": "0.9.0"},
                ),
                AuditCheck(
                    name="rich",
                    status=AuditStatus.AVAILABLE,
                    facts={"version": "13.7.0"},
                ),
                AuditCheck(
                    name="pytest",
                    status=AuditStatus.AVAILABLE,
                    facts={"version": "8.0.0"},
                ),
                AuditCheck(
                    name="ruff",
                    status=AuditStatus.AVAILABLE,
                    facts={"version": "0.1.0"},
                ),
                AuditCheck(
                    name="git",
                    status=AuditStatus.AVAILABLE,
                    facts={"version": "git version 2.40.0"},
                ),
                AuditCheck(
                    name="docker",
                    status=AuditStatus.AVAILABLE,
                    facts={"version": "Docker version 24.0.0"},
                ),
                AuditCheck(
                    name="operating_system",
                    status=AuditStatus.AVAILABLE,
                    facts={"name": "Linux", "release": "5.15.0"},
                ),
            )
        )


class StubDoctorAuditServiceWithFailures:
    """Audit service test double with some failed checks."""

    def run(self) -> AuditReport:
        return AuditReport(
            checks=(
                AuditCheck(
                    name="python",
                    status=AuditStatus.AVAILABLE,
                    facts={"version": "3.12.0"},
                ),
                AuditCheck(
                    name="virtual_environment",
                    status=AuditStatus.NOT_FOUND,
                    diagnostic="Not running inside a virtual environment",
                ),
                AuditCheck(
                    name="editable_install",
                    status=AuditStatus.NOT_FOUND,
                    diagnostic="Package not installed in editable mode",
                ),
                AuditCheck(
                    name="typer",
                    status=AuditStatus.AVAILABLE,
                    facts={"version": "0.9.0"},
                ),
                AuditCheck(
                    name="rich",
                    status=AuditStatus.AVAILABLE,
                    facts={"version": "13.7.0"},
                ),
                AuditCheck(
                    name="pytest",
                    status=AuditStatus.NOT_FOUND,
                    diagnostic="Package 'pytest' is not installed",
                ),
                AuditCheck(
                    name="ruff",
                    status=AuditStatus.AVAILABLE,
                    facts={"version": "0.1.0"},
                ),
                AuditCheck(
                    name="git",
                    status=AuditStatus.AVAILABLE,
                    facts={"version": "git version 2.40.0"},
                ),
                AuditCheck(
                    name="docker",
                    status=AuditStatus.NOT_FOUND,
                ),
                AuditCheck(
                    name="operating_system",
                    status=AuditStatus.AVAILABLE,
                    facts={"name": "Windows", "release": "11"},
                ),
            )
        )


def test_doctor_command_all_checks_pass(monkeypatch) -> None:
    """Test doctor command when all checks pass."""
    monkeypatch.setattr(cli, "doctor_audit_service", StubDoctorAuditService)

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 0
    assert "Environment Doctor" in result.stdout
    assert "Python .." in result.stdout
    assert "Virtual Environment .." in result.stdout
    assert "Editable Install .." in result.stdout
    assert "Typer .." in result.stdout
    assert "Rich .." in result.stdout
    assert "Pytest .." in result.stdout
    assert "Ruff .." in result.stdout
    assert "Git .." in result.stdout
    assert "Docker .." in result.stdout
    assert "OS ..............." in result.stdout
    assert "Environment Ready" in result.stdout


def test_doctor_command_some_checks_fail(monkeypatch) -> None:
    """Test doctor command when some checks fail."""
    monkeypatch.setattr(cli, "doctor_audit_service", StubDoctorAuditServiceWithFailures)

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 0
    assert "Environment Doctor" in result.stdout
    assert "Environment NOT Ready" in result.stdout
    assert "Recommendations:" in result.stdout
    # Should recommend venv creation
    assert "python -m venv .venv" in result.stdout
    # Should recommend pip install
    assert 'python -m pip install -e "."' in result.stdout


def test_cli_help_shows_doctor_command() -> None:
    """Test that help text includes the doctor command."""
    result = runner.invoke(cli.app, ["--help"])

    assert result.exit_code == 0
    assert "doctor" in result.stdout


def test_doctor_command_read_only_documentation() -> None:
    """Test that doctor command documentation mentions read-only behavior."""
    result = runner.invoke(cli.app, ["doctor", "--help"])

    assert result.exit_code == 0
    assert "read-only" in result.stdout.lower()
