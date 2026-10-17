"""Nombres de episodio, archivos de clip y numeración Line_XXXX."""

import pytest

from core.naming import (
    clip_audio_filename,
    clip_basename,
    clip_video_filename,
    format_episode_label,
    tsv_filename,
)
from persistence.gui_bridge import (
    export_sequence_number,
    infer_sequence_offset_from_clips,
    line_number_in_path,
    resolve_media_kind,
    segment_to_clip,
)
from persistence.models import Clip, ClipStatus


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


def test_movie_names_omit_episode_label():
    assert clip_basename("Ratatouille", "", 1) == "Ratatouille_Line_0001"
    assert clip_video_filename("Ratatouille", "", 1) == "Ratatouille_Line_0001.webm"
    assert clip_audio_filename("Ratatouille", "", 1) == "Ratatouille_Line_0001.mp3"
    assert tsv_filename("Ratatouille", "") == "Ratatouille_anki.tsv"
    assert tsv_filename("Ratatouille", "", "Anyone_Can_Cook") == (
        "Ratatouille_Anyone_Can_Cook_anki.tsv"
    )


def test_resolve_media_kind_from_filename():
    assert resolve_media_kind("Show_S02E04.mkv") == ("series", 2, 4)
    assert resolve_media_kind("Show.Episode.12.mkv") == ("series", 1, 12)
    assert resolve_media_kind("Ratatouille (2007).mkv", "Ratatouille") == ("movie", 1, 1)
    assert resolve_media_kind("movie.mkv", "Show S12E03") == ("series", 12, 3)


def test_export_sequence_skips_deleted_and_ignores_internal_id():
    segments = [
        {"id": 40, "status": "pending"},
        {"id": 7, "status": "deleted"},
        {"id": 9, "status": "exported"},
    ]
    assert export_sequence_number(segments, 40) == 1
    assert export_sequence_number(segments, 9) == 2
    assert export_sequence_number(segments, 9, offset=10) == 12
    with pytest.raises(ValueError):
        export_sequence_number(segments, 7)


def test_saved_clip_uses_internal_id_and_export_line_number():
    segments = [
        {"id": 40, "status": "pending", "text": "First", "start": 0.0, "end": 1.0},
        {"id": 7, "status": "deleted", "text": "Gone", "start": 1.0, "end": 2.0},
        {
            "id": 9,
            "status": "exported",
            "text": "Second",
            "start": 2.0,
            "end": 3.0,
            "cue_indices": [1],
        },
    ]
    sequence_number = export_sequence_number(segments, 9)
    clip = segment_to_clip(
        segments[2],
        internal_index=1,
        output_dir="output_files",
        series_name="Example_Series",
        file_episode_label="S01E01",
        sequence_number=sequence_number,
    )
    assert clip is not None
    assert clip.id == 9
    assert clip.status == ClipStatus.GENERATED
    assert clip.video_path.endswith("Example_Series_S01E01_Line_0002.webm")
    assert clip.audio_path.endswith("Example_Series_S01E01_Line_0002.mp3")
    assert "Line_0009" not in clip.video_path

    pending = segment_to_clip(
        segments[0],
        internal_index=0,
        output_dir="output_files",
        series_name="Example_Series",
        file_episode_label="S01E01",
        sequence_number=1,
    )
    assert pending.video_path == ""
    assert pending.audio_path == ""
    assert segment_to_clip(
        segments[1],
        internal_index=0,
        output_dir="output_files",
        series_name="Example_Series",
        file_episode_label="S01E01",
        sequence_number=1,
    ) is None


def test_line_number_and_sequence_offset_from_saved_paths():
    assert line_number_in_path("output_files/Example_Series_S01E01_Line_0012.webm") == 12
    assert line_number_in_path(None) is None
    assert line_number_in_path("output_files/no-number.webm") is None

    clips = [
        Clip(id=40, internal_index=0, status=ClipStatus.PENDING),
        Clip(
            id=9,
            internal_index=1,
            status=ClipStatus.GENERATED,
            video_path="output_files/Example_Series_S01E01_Line_0005.webm",
        ),
    ]
    assert infer_sequence_offset_from_clips(clips) == 3
    assert infer_sequence_offset_from_clips(
        [Clip(id=1, internal_index=0, status=ClipStatus.PENDING)]
    ) is None
