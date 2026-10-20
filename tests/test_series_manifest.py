"""Ubicación de series_manifest.json para serie y película."""

import os
from pathlib import Path

from persistence.series_manifest import manifest_dir_for_episode


def _as_root(monkeypatch, root: Path) -> None:
    monkeypatch.setattr(
        "persistence.series_manifest.project_root",
        lambda: str(root),
    )


def test_movie_does_not_get_a_manifest_dir(tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    paths = [
        project / "data" / "Pelicula",
        project / "data",
        project,
        project / "Suelta",
        tmp_path / "outside" / "Pelicula",
    ]
    _as_root(monkeypatch, project)
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
        assert manifest_dir_for_episode(str(path), "movie") is None
    assert list(tmp_path.rglob("series_manifest.json")) == []


def test_series_manifest_stays_in_the_parent_folder(tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    episode_dir = project / "data" / "Show" / "S01E01"
    episode_dir.mkdir(parents=True)
    _as_root(monkeypatch, project)
    chosen = manifest_dir_for_episode(str(episode_dir), "series")
    assert os.path.normpath(chosen) == os.path.normpath(str(project / "data" / "Show"))


def test_loose_video_in_data_keeps_the_manifest_inside_data(tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    episode_dir = project / "data"
    episode_dir.mkdir(parents=True)
    _as_root(monkeypatch, project)
    chosen = manifest_dir_for_episode(str(episode_dir), "series")
    assert os.path.normpath(chosen) == os.path.normpath(str(episode_dir))
    assert os.path.normpath(chosen) != os.path.normpath(str(project))


def test_episode_under_the_project_root_keeps_the_manifest_inside(
    tmp_path: Path, monkeypatch
):
    project = tmp_path / "proj"
    episode_dir = project / "S01E01"
    episode_dir.mkdir(parents=True)
    _as_root(monkeypatch, project)
    chosen = manifest_dir_for_episode(str(episode_dir), "series")
    assert os.path.normpath(chosen) == os.path.normpath(str(episode_dir))
    assert os.path.normpath(chosen) != os.path.normpath(str(project))


def test_video_in_the_project_root_does_not_get_a_manifest(tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    _as_root(monkeypatch, project)
    assert manifest_dir_for_episode(str(project), "series") is None


def test_external_series_keeps_the_manifest_next_to_the_episodes(
    tmp_path: Path, monkeypatch
):
    project = tmp_path / "proj"
    project.mkdir()
    episode_dir = tmp_path / "library" / "Show" / "S01E01"
    episode_dir.mkdir(parents=True)
    _as_root(monkeypatch, project)
    chosen = manifest_dir_for_episode(str(episode_dir), "series")
    assert os.path.normpath(chosen) == os.path.normpath(str(tmp_path / "library" / "Show"))
