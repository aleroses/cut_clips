"""Ubicación de series_manifest.json para serie y película."""

import os
from pathlib import Path

from persistence.series_manifest import manifest_dir_for_episode


def test_movie_does_not_get_a_manifest_dir(tmp_path: Path):
    episode_dir = tmp_path / "Movie"
    episode_dir.mkdir()
    assert manifest_dir_for_episode(str(episode_dir), "movie") is None


def test_series_manifest_stays_in_the_parent_folder(tmp_path: Path):
    episode_dir = tmp_path / "Show" / "S01E01"
    episode_dir.mkdir(parents=True)
    chosen = manifest_dir_for_episode(str(episode_dir), "series")
    assert os.path.normpath(chosen) == os.path.normpath(str(tmp_path / "Show"))


def test_episode_folder_named_data_still_uses_its_parent(tmp_path: Path):
    episode_dir = tmp_path / "data"
    episode_dir.mkdir()
    chosen = manifest_dir_for_episode(str(episode_dir), "series")
    assert os.path.normpath(chosen) == os.path.normpath(str(tmp_path))
    assert os.path.basename(chosen).lower() != "data"
