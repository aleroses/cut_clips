"""Reconstrucción segura de series_manifest.json."""

import json
import os
from pathlib import Path

from persistence.series_manifest import (
    manifest_dir_for_episode,
    read_series_manifest,
    write_series_manifest,
)
from tools.rebuild_series_manifest import main, resolve_last_sequence, scan_episode_lines

SERIES = "Todd_McFarlanes_Spawn"


def _as_root(monkeypatch, root: Path) -> None:
    monkeypatch.setattr(
        "persistence.series_manifest.project_root",
        lambda: str(root),
    )


def _clip(directory: Path, episode: str, line: int) -> None:
    output = directory / episode / "output_files"
    output.mkdir(parents=True)
    (output / f"{SERIES}_{episode}_Line_{line:04d}.webm").write_bytes(b"webm")


def _clip_in(episode_dir: Path, label: str, line: int) -> None:
    output = episode_dir / "output_files"
    output.mkdir(parents=True)
    (output / f"{SERIES}_{label}_Line_{line:04d}.webm").write_bytes(b"webm")


def _layout(root: Path) -> Path:
    series = root / "Spawn_S01"
    _clip(series, "S01E02", 2000)
    _clip(series, "S01E03", 546)
    (series / "S01E04" / "output_files").mkdir(parents=True)
    return series


def test_scan_uses_the_highest_episode_that_has_clips(tmp_path: Path):
    series = _layout(tmp_path)
    found = scan_episode_lines(str(series), SERIES)
    assert found[(1, 2)] == 2000
    assert found[(1, 3)] == 546
    assert (1, 4) not in found
    assert resolve_last_sequence(found) == 546


def test_last_episode_ignores_later_chapters_and_manual_line_is_a_fallback():
    found = {(1, 3): 546, (1, 4): 600}
    assert resolve_last_sequence(found, last_season=1, last_episode=3) == 546
    assert resolve_last_sequence({}, last_line=546) == 546


def test_dry_run_does_not_write(tmp_path: Path, capsys):
    series = _layout(tmp_path)
    code = main(["--series-dir", str(series), "--series-name", SERIES])
    assert code == 0
    assert not (series / "series_manifest.json").exists()
    captured = capsys.readouterr()
    assert "546" in captured.out
    assert "Dry-run" in captured.out


def test_apply_refuses_to_overwrite_without_force(tmp_path: Path):
    series = _layout(tmp_path)
    write_series_manifest(str(series), 10, series_name=SERIES)
    code = main(["--series-dir", str(series), "--series-name", SERIES, "--apply"])
    assert code == 1
    data = read_series_manifest(str(series))
    assert data["last_sequence_number"] == 10
    assert not (series / "series_manifest.json.bak").exists()


def test_force_writes_a_backup_and_the_rebuilt_manifest(tmp_path: Path):
    series = _layout(tmp_path)
    write_series_manifest(str(series), 10, series_name=SERIES)
    code = main(
        ["--series-dir", str(series), "--series-name", SERIES, "--apply", "--force"]
    )
    assert code == 0
    bak = json.loads((series / "series_manifest.json.bak").read_text(encoding="utf-8"))
    assert bak["last_sequence_number"] == 10
    data = read_series_manifest(str(series), expected_series_name=SERIES)
    assert data == {
        "last_sequence_number": 546,
        "series_name": SERIES,
    }
    assert set(data) == {"last_sequence_number", "series_name"}
    assert max(0, int(data["last_sequence_number"])) == 546


def test_missing_clips_and_missing_last_line_fail_without_inventing(tmp_path: Path):
    series = tmp_path / "empty"
    series.mkdir()
    code = main(["--series-dir", str(series), "--series-name", SERIES, "--apply"])
    assert code == 1
    assert not (series / "series_manifest.json").exists()
    names = os.listdir(series)
    assert names == []


def test_rebuild_lands_in_the_same_dir_as_manifest_dir_for_episode(
    tmp_path: Path, monkeypatch
):
    project = tmp_path / "proj"
    episode = project / "data" / "Show" / "S01E01"
    _as_root(monkeypatch, project)
    _clip_in(episode, "S01E01", 12)
    series = episode.parent
    code = main(["--series-dir", str(series), "--series-name", SERIES, "--apply"])
    assert code == 0
    expected = Path(manifest_dir_for_episode(str(episode), "series"))
    assert expected == series
    assert (expected / "series_manifest.json").is_file()
    assert not (project / "series_manifest.json").exists()


def test_rebuild_loose_video_in_data_stays_out_of_the_project_root(
    tmp_path: Path, monkeypatch
):
    project = tmp_path / "proj"
    episode = project / "data"
    _as_root(monkeypatch, project)
    _clip_in(episode, "S01E01", 4)
    code = main(["--series-dir", str(project), "--series-name", SERIES, "--apply"])
    assert code == 0
    expected = Path(manifest_dir_for_episode(str(episode), "series"))
    assert expected == episode
    assert (episode / "series_manifest.json").is_file()
    assert not (project / "series_manifest.json").exists()


def test_rebuild_episode_under_the_root_stays_inside_the_episode(
    tmp_path: Path, monkeypatch
):
    project = tmp_path / "proj"
    episode = project / "S01E01"
    _as_root(monkeypatch, project)
    _clip_in(episode, "S01E01", 8)
    code = main(["--series-dir", str(project), "--series-name", SERIES, "--apply"])
    assert code == 0
    expected = Path(manifest_dir_for_episode(str(episode), "series"))
    assert expected == episode
    assert (episode / "series_manifest.json").is_file()
    assert not (project / "series_manifest.json").exists()


def test_rebuild_video_in_the_project_root_writes_nothing(tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    _as_root(monkeypatch, project)
    _clip_in(project, "S01E01", 3)
    code = main(["--series-dir", str(tmp_path), "--series-name", SERIES, "--apply"])
    assert code == 1
    assert manifest_dir_for_episode(str(project), "series") is None
    assert list(tmp_path.rglob("series_manifest.json")) == []


def test_rebuild_external_series_stays_next_to_the_episodes(tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    episode = tmp_path / "library" / "Show" / "S01E02"
    _as_root(monkeypatch, project)
    _clip_in(episode, "S01E02", 9)
    series = episode.parent
    code = main(["--series-dir", str(series), "--series-name", SERIES, "--apply"])
    assert code == 0
    expected = Path(manifest_dir_for_episode(str(episode), "series"))
    assert expected == series
    assert (series / "series_manifest.json").is_file()
