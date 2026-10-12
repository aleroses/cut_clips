"""Guardado y carga JSON de un proyecto sintético."""

import json
from pathlib import Path

import pytest

from persistence.models import SCHEMA_VERSION, ClipStatus, Episode, Project
from persistence.store import load_project, save_project

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project.json"


def test_fixture_round_trip_preserves_project_fields(tmp_path):
    loaded = load_project(str(FIXTURE))
    assert loaded.modified is False
    assert SCHEMA_VERSION == 1
    assert loaded.to_dict()["schema_version"] == 1
    assert loaded.series_name == "Example_Series"
    assert loaded.root_dir == "series_root"
    assert loaded.last_clip_id == 2
    assert len(loaded.episodes) == 1

    episode = loaded.episodes[0]
    assert episode.video_path == "videos/Episode One.mkv"
    assert episode.episode_label == "S01-Ep01"
    assert episode.episode_title == "Pilot"
    assert episode.subtitle_path == "videos/Episode One.srt"
    assert episode.subtitle_track_index == 2
    assert episode.padding_start == 0.25
    assert episode.padding_end == 0.4
    assert episode.output_dir == "output_files"
    assert episode.media_info["gui_parser_options"]["language"] == "en"
    assert episode.subtitles[0].text == "Hello there."
    assert episode.translation.provider == "none"
    assert episode.translation.cache_path == ""

    clip = episode.clips[0]
    assert clip.id == 2
    assert clip.internal_index == 0
    assert clip.subtitle_indices == [0]
    assert clip.status == ClipStatus.GENERATED
    assert clip.translation == "Hola."
    assert clip.video_path == "output_files/Example_Series_S01E01_Line_0001.webm"
    assert clip.audio_path == "output_files/Example_Series_S01E01_Line_0001.mp3"
    assert clip.generation_fingerprint["text"] == "Hello there."
    assert clip.error_message == ""

    destination = tmp_path / "saved.anki-project.json"
    save_project(loaded, str(destination))
    assert loaded.modified is False
    assert not list(tmp_path.glob(".anki_project_*"))
    again = load_project(str(destination))
    assert again.to_dict() == loaded.to_dict()
    raw = json.loads(destination.read_text(encoding="utf-8"))
    assert raw["schema_version"] == 1
    assert raw["episodes"][0]["clips"][0]["status"] == "generated"


def test_missing_schema_version_defaults_to_one_and_unknown_version_is_rejected():
    project = Project.from_dict({})
    assert project.to_dict()["schema_version"] == 1
    assert project.series_name == ""
    assert project.root_dir == "."
    assert project.last_clip_id == 0
    assert project.episodes == []

    episode = Episode.from_dict({"season": 2, "episode": 3})
    assert episode.episode_label == "S02-Ep03"
    assert episode.padding_start == 0.0
    assert episode.output_dir == "output_files"
    assert episode.subtitle_track_index is None

    with pytest.raises(ValueError, match="Versión de esquema no soportada"):
        Project.from_dict({"schema_version": 2, "episodes": []})
