"""media_kind en el episodio y nombre sugerido del proyecto."""

import json
import os

from core.naming import choose_tsv_basename, tsv_lock_after_mode_change
from persistence.gui_bridge import build_project_from_gui, load_gui_state_from_project
from persistence.models import SCHEMA_VERSION, Episode, Project
from persistence.store import default_project_path, load_project, save_project
from ui.parser_options_widget import ParserOptions


def test_old_episode_without_media_kind_stays_series_and_keeps_label():
    episode = Episode.from_dict({"episode_label": "S01-Ep01", "season": 1, "episode": 1})
    assert episode.media_kind == "series"
    assert episode.episode_label == "S01-Ep01"


def test_movie_episode_clears_label_after_legacy_fill():
    episode = Episode.from_dict({"media_kind": "movie", "episode_label": "S01-Ep01"})
    assert episode.media_kind == "movie"
    assert episode.episode_label == ""


def test_save_load_round_trip_keeps_series_and_movie(tmp_path):
    series = Project(
        series_name="Nombre",
        episodes=[Episode(episode_label="S01-Ep01", season=1, episode=1)],
    )
    movie = Project(
        series_name="Nombre",
        episodes=[Episode(media_kind="movie", episode_label="S01-Ep01", season=1, episode=1)],
    )

    series_path = tmp_path / "series.anki-project.json"
    movie_path = tmp_path / "movie.anki-project.json"
    save_project(series, str(series_path))
    save_project(movie, str(movie_path))

    loaded_series = load_project(str(series_path))
    loaded_movie = load_project(str(movie_path))

    assert loaded_series.to_dict()["schema_version"] == 1
    assert SCHEMA_VERSION == 1
    assert loaded_series.episodes[0].media_kind == "series"
    assert loaded_series.episodes[0].episode_label == "S01-Ep01"
    assert loaded_movie.episodes[0].media_kind == "movie"
    assert loaded_movie.episodes[0].episode_label == ""

    raw_series = json.loads(series_path.read_text(encoding="utf-8"))
    raw_movie = json.loads(movie_path.read_text(encoding="utf-8"))
    assert raw_series["schema_version"] == 1
    assert raw_series["episodes"][0]["media_kind"] == "series"
    assert raw_movie["episodes"][0]["media_kind"] == "movie"
    assert raw_movie["episodes"][0]["episode_label"] == ""


def test_legacy_project_json_without_media_kind_loads_as_series(tmp_path):
    path = tmp_path / "legacy.anki-project.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "series_name": "Nombre",
                "root_dir": ".",
                "last_clip_id": 0,
                "episodes": [
                    {
                        "season": 1,
                        "episode": 1,
                        "episode_label": "S01-Ep01",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    loaded = load_project(str(path))
    episode = loaded.episodes[0]
    assert episode.media_kind == "series"
    assert episode.episode_label == "S01-Ep01"


def test_default_project_path_omits_label_for_movies(tmp_path):
    series_path = default_project_path("Nombre", "S01E01", str(tmp_path))
    movie_path = default_project_path("Nombre", "", str(tmp_path))
    assert os.path.basename(series_path) == "Nombre_S01E01.anki-project.json"
    assert os.path.basename(movie_path) == "Nombre.anki-project.json"
    assert series_path == os.path.join(str(tmp_path), "Nombre_S01E01.anki-project.json")
    assert movie_path == os.path.join(str(tmp_path), "Nombre.anki-project.json")


def _exported_segment():
    return {
        "id": 1,
        "status": "exported",
        "text": "Hello",
        "start": 0.0,
        "end": 1.0,
        "cue_indices": [],
    }


def _build(media_kind=None):
    kwargs = dict(
        series_name="Nombre",
        season=1,
        episode_num=1,
        video_path="/tmp/video.mkv",
        episode_title="",
        subtitle_path="",
        subtitle_track_index=None,
        subtitle_language="en",
        audio_track=0,
        video_track=0,
        media_summary=None,
        parser_options=ParserOptions(),
        cue_map={},
        segments=[_exported_segment()],
        translation_provider="none",
        last_clip_id=1,
        root_dir=".",
    )
    if media_kind is not None:
        kwargs["media_kind"] = media_kind
    return build_project_from_gui(**kwargs)


def test_build_project_without_media_kind_stays_series():
    project = _build()
    episode = project.episodes[0]
    assert episode.media_kind == "series"
    assert episode.episode_label == "S01-Ep01"
    assert episode.clips[0].video_path.endswith("Nombre_S01E01_Line_0001.webm")


def test_build_project_movie_omits_episode_label():
    project = _build("movie")
    episode = project.episodes[0]
    assert episode.media_kind == "movie"
    assert episode.episode_label == ""
    assert episode.clips[0].video_path.endswith("Nombre_Line_0001.webm")


def test_load_gui_state_from_legacy_json_keeps_series_and_clip_path(tmp_path):
    clip_path = "output_files/Nombre_S01E01_Line_0001.webm"
    path = tmp_path / "legacy.anki-project.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "series_name": "Nombre",
                "root_dir": ".",
                "last_clip_id": 1,
                "episodes": [
                    {
                        "season": 1,
                        "episode": 1,
                        "episode_label": "S01-Ep01",
                        "clips": [
                            {
                                "id": 1,
                                "status": "generated",
                                "text": "Hello",
                                "start": 0.0,
                                "end": 1.0,
                                "video_path": clip_path,
                                "audio_path": "output_files/Nombre_S01E01_Line_0001.mp3",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    project = load_project(str(path))
    state = load_gui_state_from_project(project)
    assert state.media_kind == "series"
    assert project.episodes[0].episode_label == "S01-Ep01"
    assert project.episodes[0].clips[0].video_path == clip_path


def test_load_gui_state_round_trip_movie(tmp_path):
    project = _build("movie")
    path = tmp_path / "movie.anki-project.json"
    save_project(project, str(path))
    loaded = load_project(str(path))
    state = load_gui_state_from_project(loaded)
    assert state.media_kind == "movie"
    assert loaded.episodes[0].episode_label == ""
    assert loaded.episodes[0].clips[0].video_path.endswith("Nombre_Line_0001.webm")


def test_generated_clip_keeps_its_path_when_saved_as_movie():
    stored_video = "output_files/Nombre_S01E04_Line_0547.webm"
    stored_audio = "output_files/Nombre_S01E04_Line_0547.mp3"
    generated = _exported_segment()
    generated["video_path"] = stored_video
    generated["audio_path"] = stored_audio
    pending = {
        "id": 2,
        "status": "pending",
        "text": "Next",
        "start": 1.0,
        "end": 2.0,
        "cue_indices": [],
    }
    project = build_project_from_gui(
        series_name="Nombre",
        season=1,
        episode_num=4,
        video_path="/tmp/video.mkv",
        episode_title="Dominoes",
        subtitle_path="",
        subtitle_track_index=None,
        subtitle_language="en",
        audio_track=0,
        video_track=0,
        media_summary=None,
        parser_options=ParserOptions(),
        cue_map={},
        segments=[generated, pending],
        translation_provider="none",
        last_clip_id=2,
        root_dir=".",
        media_kind="movie",
    )
    episode = project.episodes[0]
    assert episode.media_kind == "movie"
    assert episode.episode_label == ""
    assert episode.clips[0].video_path == stored_video
    assert episode.clips[0].audio_path == stored_audio
    assert episode.clips[1].video_path == ""
    assert episode.clips[1].audio_path == ""


def test_loaded_segment_remembers_generated_paths(tmp_path):
    project = _build()
    path = tmp_path / "series.anki-project.json"
    save_project(project, str(path))
    state = load_gui_state_from_project(load_project(str(path)))
    segment = state.segments[0]
    assert segment["video_path"].endswith("Nombre_S01E01_Line_0001.webm")
    assert segment["audio_path"].endswith("Nombre_S01E01_Line_0001.mp3")


def test_existing_tsv_name_stays_after_mode_change():
    previous = "Nombre_S01E04_Dominoes_anki.tsv"
    movie_name = "Nombre_Dominoes_anki.tsv"
    locked = tsv_lock_after_mode_change(None, previous, True)
    assert locked == previous
    assert choose_tsv_basename(movie_name, locked) == previous
    assert tsv_lock_after_mode_change(locked, movie_name, True) == previous


def test_new_movie_tsv_name_is_used_when_none_exists():
    assert tsv_lock_after_mode_change(None, "Nombre_S01E01_anki.tsv", False) is None
    assert choose_tsv_basename("Nombre_anki.tsv", None) == "Nombre_anki.tsv"
