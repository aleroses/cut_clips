"""SRT externo como bloques con tiempo y texto limpio."""

from core.subtitle_text import (
    REFERENCE_MATCH_TOLERANCE_SEC,
    load_reference_cues,
    reference_text_for_range,
)


SRT_BODY = """1
00:00:01,000 --> 00:00:02,000
<i>El niño</i> (reporter) está en el café.

2
00:00:03,000 --> 00:00:04,000
[music]

3
00:00:05,000 --> 00:00:06,000
Subtitles by OpenSubtitles.org
"""


def test_utf8_srt_loads_cleaned_timed_cues(tmp_path):
    path = tmp_path / "ref.srt"
    path.write_bytes(SRT_BODY.encode("utf-8"))

    cues = load_reference_cues(path)

    assert cues == [{
        "start": 1.0,
        "end": 2.0,
        "text": "El niño está en el café.",
    }]


def test_windows1252_srt_keeps_enie(tmp_path):
    path = tmp_path / "ref.srt"
    path.write_bytes(SRT_BODY.encode("cp1252"))

    cues = load_reference_cues(path)

    assert len(cues) == 1
    assert cues[0]["text"] == "El niño está en el café."
    assert cues[0]["start"] == 1.0


def test_exact_overlap_returns_that_cue():
    cues = [{"start": 1.0, "end": 2.0, "text": "Hola"}]
    assert reference_text_for_range(cues, 1.0, 2.0) == "Hola"


def test_partial_overlap_is_included():
    cues = [{"start": 1.8, "end": 2.4, "text": "niño"}]
    assert reference_text_for_range(cues, 1.0, 2.0) == "niño"


def test_no_overlap_returns_empty():
    cues = [{"start": 10.0, "end": 11.0, "text": "lejos"}]
    assert reference_text_for_range(cues, 1.0, 2.0) == ""


def test_several_blocks_join_in_order():
    cues = [
        {"start": 1.0, "end": 1.4, "text": "Hola"},
        {"start": 1.4, "end": 2.0, "text": "niño"},
    ]
    assert reference_text_for_range(cues, 1.0, 2.0) == "Hola niño"


def test_tolerance_includes_nearby_and_skips_farther():
    assert REFERENCE_MATCH_TOLERANCE_SEC == 0.5
    near = [{"start": 2.4, "end": 3.0, "text": "cerca"}]
    far = [{"start": 2.6, "end": 3.2, "text": "lejos"}]
    assert reference_text_for_range(near, 1.0, 2.0) == "cerca"
    assert reference_text_for_range(far, 1.0, 2.0) == ""
