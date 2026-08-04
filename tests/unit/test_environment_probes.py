"""Unit tests for environment probes."""

import importlib.metadata
import sys
from unittest.mock import patch

from ai_engineering_bootstrap.models import AuditStatus
from ai_engineering_bootstrap.probes.environment import (
    EditableInstallProbe,
    PythonPackageProbe,
    VirtualEnvironmentProbe,
)


class TestVirtualEnvironmentProbe:
    """Tests for the virtual environment probe."""

    def test_in_venv_with_base_prefix(self) -> None:
        """Test detection when base_prefix differs from prefix."""
        with (
            patch.object(sys, "base_prefix", "/usr"),
            patch.object(sys, "prefix", "/home/user/.venv"),
        ):
            check = VirtualEnvironmentProbe().run()

        assert check.status is AuditStatus.AVAILABLE
        assert check.facts["path"] == "/home/user/.venv"

    def test_not_in_venv(self) -> None:
        """Test detection when not in a virtual environment."""
        with patch.object(sys, "base_prefix", sys.prefix):
            check = VirtualEnvironmentProbe().run()

        assert check.status is AuditStatus.NOT_FOUND
        assert "Not running inside" in check.diagnostic

    def test_in_venv_with_real_prefix(self) -> None:
        """Test detection using real_prefix attribute (older Python)."""
        # Add real_prefix to sys for testing purposes
        original_has_real_prefix = hasattr(sys, "real_prefix")
        if not original_has_real_prefix:
            sys.real_prefix = "/usr"  # type: ignore[attr-defined]

        try:
            with (
                patch.object(sys, "prefix", "/home/user/.venv"),
                patch.object(sys, "base_prefix", "/home/user/.venv"),
            ):
                check = VirtualEnvironmentProbe().run()

            assert check.status is AuditStatus.AVAILABLE
        finally:
            if not original_has_real_prefix:
                delattr(sys, "real_prefix")


class TestEditableInstallProbe:
    """Tests for the editable install probe."""

    def test_editable_install_detected(self) -> None:
        """Test detection of editable installation."""
        mock_dist = type(
            "MockDist",
            (),
            {
                "read_text": lambda self, name: (
                    '{"url": "file:///home/user/project"}'
                    if name == "direct_url.json"
                    else None
                ),
            },
        )()

        with patch.object(importlib.metadata, "distribution", return_value=mock_dist):
            check = EditableInstallProbe().run()

        assert check.status is AuditStatus.AVAILABLE
        assert check.facts["package"] == "ai-engineering-bootstrap"

    def test_package_not_found(self) -> None:
        """Test when package is not installed."""
        with patch.object(
            importlib.metadata,
            "distribution",
            side_effect=importlib.metadata.PackageNotFoundError,
        ):
            check = EditableInstallProbe().run()

        assert check.status is AuditStatus.NOT_FOUND
        assert "not installed in editable mode" in check.diagnostic

    def test_no_direct_url_json(self) -> None:
        """Test when direct_url.json doesn't exist (non-editable install)."""
        mock_dist = type("MockDist", (), {"read_text": lambda self, name: None})()

        with patch.object(importlib.metadata, "distribution", return_value=mock_dist):
            check = EditableInstallProbe().run()

        assert check.status is AuditStatus.NOT_FOUND


class TestPythonPackageProbe:
    """Tests for the Python package availability probe."""

    def test_package_available(self) -> None:
        """Test when package is installed."""
        with patch.object(importlib.metadata, "version", return_value="0.29.0"):
            check = PythonPackageProbe("typer").run()

        assert check.status is AuditStatus.AVAILABLE
        assert check.name == "typer"
        assert check.facts["version"] == "0.29.0"

    def test_package_not_found(self) -> None:
        """Test when package is not installed."""
        with patch.object(
            importlib.metadata,
            "version",
            side_effect=importlib.metadata.PackageNotFoundError,
        ):
            check = PythonPackageProbe("missing-package").run()

        assert check.status is AuditStatus.NOT_FOUND
        assert "missing-package" in check.diagnostic

    def test_package_error(self) -> None:
        """Test when an unexpected error occurs."""
        with patch.object(
            importlib.metadata, "version", side_effect=Exception("unexpected error")
        ):
            check = PythonPackageProbe("some-package").run()

        assert check.status is AuditStatus.ERROR
        assert check.diagnostic == "unexpected error"

    def test_package_name_lowercased(self) -> None:
        """Test that package name is lowercased in result."""
        with patch.object(importlib.metadata, "version", return_value="1.0.0"):
            check = PythonPackageProbe("MyPackage").run()

        assert check.name == "mypackage"
