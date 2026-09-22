"""Guardado y carga de proyectos en JSON."""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any

from persistence.models import Project, SCHEMA_VERSION


def project_to_dict(project: Project) -> dict[str, Any]:
    return project.to_dict()


def project_from_dict(data: dict[str, Any]) -> Project:
    return Project.from_dict(data)


def save_project(project: Project, path: str) -> None:
    """Guarda el proyecto en JSON (escritura atómica)."""
    data = project.to_dict()
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        suffix=".json", prefix=".anki_project_", dir=directory or None
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_path, path)
        project.modified = False
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def load_project(path: str) -> Project:
    """Carga un proyecto desde JSON."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    project = Project.from_dict(data)
    project.modified = False
    return project


def default_project_path(series_name: str, episode_label: str, root_dir: str = ".") -> str:
    """Ruta sugerida para el archivo de proyecto de un episodio."""
    safe_series = series_name.replace(" ", "_") or "project"
    return os.path.join(root_dir, f"{safe_series}_{episode_label}.anki-project.json")
