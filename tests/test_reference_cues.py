"""SRT externo como bloques con tiempo y texto limpio."""

from core.subtitle_text import load_reference_cues


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
