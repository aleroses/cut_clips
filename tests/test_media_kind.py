"""media_kind en el episodio y nombre sugerido del proyecto."""

import json
import os

from persistence.models import SCHEMA_VERSION, Episode, Project
from persistence.store import default_project_path, load_project, save_project


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
