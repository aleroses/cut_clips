"""Manifiesto más alto que los clips de los capítulos anteriores."""

import json
from pathlib import Path

from persistence.series_manifest import (
    confirm_lower_series_manifest,
    episode_output_has_clips,
    highest_prior_line,
    read_series_manifest,
    stale_manifest_bounds,
    write_series_manifest,
)

SERIES = "Todd_McFarlanes_Spawn"


def _clip(series: Path, episode: str, line: int) -> None:
    output = series / episode / "output_files"
    output.mkdir(parents=True)
    (output / f"{SERIES}_{episode}_Line_{line:04d}.webm").write_bytes(b"webm")


def _layout(tmp_path: Path) -> Path:
    series = tmp_path / "Spawn_S01"
    _clip(series, "S01E03", 546)
    _clip(series, "S01E05", 900)
    write_series_manifest(str(series), 550, series_name=SERIES)
    return series


def test_no_gap_when_the_manifest_matches_the_prior_line(tmp_path: Path):
    series = _layout(tmp_path)
    prior = highest_prior_line(str(series), SERIES, 1, 4)
    assert prior == 546
    assert stale_manifest_bounds(
        media_kind="series",
        manifest_last=546,
        prior_line=prior,
        episode_has_clips=False,
    ) is None


def test_gap_uses_the_previous_episode_and_ignores_a_later_one(tmp_path: Path):
    series = _layout(tmp_path)
    prior = highest_prior_line(str(series), SERIES, 1, 4)
    assert prior == 546
    assert stale_manifest_bounds(
        media_kind="series",
        manifest_last=550,
        prior_line=prior,
        episode_has_clips=False,
    ) == (550, 546)


def test_no_prompt_without_previous_episodes(tmp_path: Path):
    series = tmp_path / "Spawn_S01"
    _clip(series, "S01E04", 12)
    assert highest_prior_line(str(series), SERIES, 1, 4) is None
    assert stale_manifest_bounds(
        media_kind="series",
        manifest_last=550,
        prior_line=None,
        episode_has_clips=False,
    ) is None


def test_episode_with_clips_is_not_checked(tmp_path: Path):
    series = _layout(tmp_path)
    current = series / "S01E04" / "output_files"
    current.mkdir(parents=True)
    (current / f"{SERIES}_S01E04_Line_0551.webm").write_bytes(b"webm")
    assert episode_output_has_clips(str(current), SERIES, 1, 4) is True
    assert stale_manifest_bounds(
        media_kind="series",
        manifest_last=550,
        prior_line=546,
        episode_has_clips=True,
    ) is None


def test_movie_never_prompts(tmp_path: Path):
    series = _layout(tmp_path)
    prior = highest_prior_line(str(series), SERIES, 1, 4)
    assert stale_manifest_bounds(
        media_kind="movie",
        manifest_last=550,
        prior_line=prior,
        episode_has_clips=False,
    ) is None


def test_declining_does_not_change_the_manifest(tmp_path: Path):
    series = _layout(tmp_path)
    path = series / "series_manifest.json"
    original = path.read_bytes()
    changed = confirm_lower_series_manifest(
        str(series), 546, series_name=SERIES, accept=False
    )
    assert changed is False
    assert path.read_bytes() == original
    assert not (series / "series_manifest.json.bak").exists()
    data = read_series_manifest(str(series), expected_series_name=SERIES)
    assert data["last_sequence_number"] == 550


def test_accepting_writes_a_backup_and_lowers_the_manifest(tmp_path: Path):
    series = _layout(tmp_path)
    changed = confirm_lower_series_manifest(
        str(series), 546, series_name=SERIES, accept=True
    )
    assert changed is True
    bak = json.loads((series / "series_manifest.json.bak").read_text(encoding="utf-8"))
    assert bak["last_sequence_number"] == 550
    data = read_series_manifest(str(series), expected_series_name=SERIES)
    assert data == {"last_sequence_number": 546, "series_name": SERIES}
    assert set(data) == {"last_sequence_number", "series_name"}
