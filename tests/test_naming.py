"""Nombres de episodio, archivos de clip y TSV."""

from core.naming import (
    clip_audio_filename,
    clip_basename,
    clip_video_filename,
    format_episode_label,
    tsv_filename,
)
from persistence.gui_bridge import resolve_media_kind


def test_episode_labels_legacy_and_compact():
    assert format_episode_label(1, 1) == "S01-Ep01"
    assert format_episode_label(1, 1, style="legacy") == "S01-Ep01"
    assert format_episode_label(12, 3, style="compact") == "S12E03"
    assert format_episode_label(2, 4, style="otro") == "S02-Ep04"


def test_media_filenames_use_line_padding():
    assert clip_basename("Example_Series", "S01E01", 1) == (
        "Example_Series_S01E01_Line_0001"
    )
    assert clip_video_filename("Example_Series", "S01E01", 1) == (
        "Example_Series_S01E01_Line_0001.webm"
    )
    assert clip_audio_filename("Example_Series", "S01E01", 12) == (
        "Example_Series_S01E01_Line_0012.mp3"
    )


def test_tsv_filename_with_and_without_title():
    assert tsv_filename("Example_Series", "S01E01") == (
        "Example_Series_S01E01_anki.tsv"
    )
    assert tsv_filename("Example_Series", "S01E01", "Pilot") == (
        "Example_Series_S01E01_Pilot_anki.tsv"
    )


def test_resolve_media_kind_from_filename_and_title():
    assert resolve_media_kind("showtest_S01E04.mkv") == ("series", 1, 4)
    assert resolve_media_kind("showtest Episode 12.mkv") == ("series", 1, 12)
    assert resolve_media_kind("Ratatouille (2007).mkv") == ("movie", 1, 1)
    assert resolve_media_kind("Show_S02E04.mkv") == ("series", 2, 4)
    assert resolve_media_kind("show_s02e04.mkv") == ("series", 2, 4)
    assert resolve_media_kind("movie.mkv", "Show S12E03") == ("series", 12, 3)
    assert resolve_media_kind("Ratatouille (2007).mkv", "Ratatouille") == ("movie", 1, 1)
    assert resolve_media_kind("Blade Runner 2049.mkv") == ("movie", 1, 1)
    assert resolve_media_kind("Apollo 13.mkv") == ("movie", 1, 1)


def test_movie_names_omit_episode_label():
    assert clip_basename("Ratatouille", "", 1) == "Ratatouille_Line_0001"
    assert clip_video_filename("Ratatouille", "", 1) == "Ratatouille_Line_0001.webm"
    assert clip_audio_filename("Ratatouille", "", 1) == "Ratatouille_Line_0001.mp3"
    assert tsv_filename("Ratatouille", "") == "Ratatouille_anki.tsv"
    assert tsv_filename("Ratatouille", "", "Anyone_Can_Cook") == (
        "Ratatouille_Anyone_Can_Cook_anki.tsv"
    )
