"""Template discovery and safe filesystem project generation."""

from __future__ import annotations

import re
import shutil
import sysconfig
import tempfile
from collections.abc import Sequence
from pathlib import Path

from ai_engineering_bootstrap.exceptions import (
    DestinationConflictError,
    GenerationError,
    InvalidProjectNameError,
    TemplateNotFoundError,
    UnsupportedTemplateError,
)
from ai_engineering_bootstrap.models import (
    GenerationRequest,
    GenerationResult,
    TemplateInfo,
)

_PROJECT_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_SUPPORTED_TEMPLATE = "ai-app-template-v1"
_PLACEHOLDER = "{{ project_name }}"
_TEXT_SUFFIXES = {".json", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"}
_TEXT_NAMES = {".env.example", ".gitignore", "Dockerfile", "Makefile"}


def default_templates_root() -> Path:
    """Return templates from a source checkout or installed package data."""
    source_templates = Path(__file__).resolve().parents[2] / "templates"
    if source_templates.is_dir():
        return source_templates
    return (
        Path(sysconfig.get_path("data"))
        / "share"
        / "ai-engineering-bootstrap"
        / "templates"
    )


class FileSystemTemplateCatalog:
    """Discover templates stored under a configured directory."""

    def __init__(self, templates_root: Path) -> None:
        self._templates_root = templates_root

    def list_templates(self) -> Sequence[TemplateInfo]:
        """Return template directories in deterministic order."""
        if not self._templates_root.is_dir():
            return ()
        return tuple(
            TemplateInfo(template_id=path.name, source=path)
            for path in sorted(
                self._templates_root.iterdir(), key=lambda item: item.name
            )
            if path.is_dir()
        )

    def get_template(self, template_id: str) -> TemplateInfo:
        """Return an exact template match."""
        for template in self.list_templates():
            if template.template_id == template_id:
                return template
        raise TemplateNotFoundError(f"Unknown template: {template_id}")


class FileSystemProjectGenerator:
    """Copy and render a declared template into a new project directory."""

    def __init__(self, catalog: FileSystemTemplateCatalog) -> None:
        self._catalog = catalog

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Create a staged project and leave existing targets untouched."""
        self._validate_project_name(request.project_name)
        if request.template_id != _SUPPORTED_TEMPLATE:
            raise UnsupportedTemplateError(
                f"Template generation is not implemented: {request.template_id}"
            )

        template = self._catalog.get_template(request.template_id)
        destination_parent = request.destination.resolve()
        project_path = destination_parent / request.project_name
        if project_path.exists():
            raise DestinationConflictError(
                f"Destination already exists: {project_path}"
            )
        if not destination_parent.is_dir():
            raise GenerationError(
                f"Destination directory does not exist: {destination_parent}"
            )

        try:
            with tempfile.TemporaryDirectory(
                prefix=".ai-bootstrap-", dir=destination_parent
            ) as staging_directory:
                staged_project = Path(staging_directory) / request.project_name
                shutil.copytree(template.source, staged_project)
                self._render_text_files(staged_project, request.project_name)
                staged_project.replace(project_path)
        except (OSError, UnicodeError) as error:
            raise GenerationError(f"Project creation failed: {error}") from error

        return GenerationResult(
            project_name=request.project_name,
            template_id=request.template_id,
            project_path=project_path,
        )

    @staticmethod
    def _validate_project_name(project_name: str) -> None:
        if not _PROJECT_NAME_PATTERN.fullmatch(project_name):
            raise InvalidProjectNameError(
                "Project name must start with a letter and contain only letters, "
                "numbers, hyphens, or underscores."
            )

    @staticmethod
    def _render_text_files(project_root: Path, project_name: str) -> None:
        for path in project_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in _TEXT_SUFFIXES and path.name not in _TEXT_NAMES:
                continue
            content = path.read_text(encoding="utf-8")
            rendered = content.replace(_PLACEHOLDER, project_name)
            if rendered != content:
                path.write_text(rendered, encoding="utf-8")


def default_template_catalog() -> FileSystemTemplateCatalog:
    """Build the catalog for repository templates."""
    return FileSystemTemplateCatalog(default_templates_root())


def default_project_generator() -> FileSystemProjectGenerator:
    """Build the filesystem project generator."""
    return FileSystemProjectGenerator(default_template_catalog())
