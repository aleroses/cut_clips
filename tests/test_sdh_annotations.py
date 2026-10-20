"""Anotaciones SDH al crear oraciones desde un SRT de vídeo."""

import json

from core.subtitle_parser import SDH_ANNOTATION_MAX_WORDS, generate_sentences
from persistence.gui_bridge import load_gui_state_from_project
from persistence.store import load_project


def _timestamp(seconds: float) -> str:
    whole = int(seconds)
    millis = int(round((seconds - whole) * 1000))
    minutes, secs = divmod(whole, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _write_srt(path, cues: list[tuple[float, float, str]]) -> None:
    blocks = []
    for index, (start, end, text) in enumerate(cues, start=1):
        blocks.append(f"{index}\n{_timestamp(start)} --> {_timestamp(end)}\n{text}\n")
    path.write_text("\n".join(blocks), encoding="utf-8")


def _sentences(tmp_path, name: str, cues: list[tuple[float, float, str]]) -> list[dict]:
    path = tmp_path / name
    _write_srt(path, cues)
    return generate_sentences(path)["sentences"]


def test_reporter_annotation_with_inner_spaces_is_removed(tmp_path):
    sentences = _sentences(tmp_path, "reporter.srt", [
        (1.0, 3.0, "( reporter ) Asked to possibly re-open the Kyle Watson case..."),
    ])
    assert sentences[0]["text"] == (
        "Asked to possibly re-open the Kyle Watson case..."
    )


def test_screams_only_does_not_create_a_clip(tmp_path):
    sentences = _sentences(tmp_path, "screams.srt", [
        (1.0, 2.0, "(screams)"),
    ])
    assert sentences == []


def test_music_bracket_does_not_create_a_clip(tmp_path):
    sentences = _sentences(tmp_path, "music.srt", [
        (1.0, 2.0, "[music]"),
    ])
    assert sentences == []


def test_long_parenthesis_stays_and_four_words_go(tmp_path):
    assert SDH_ANNOTATION_MAX_WORDS == 4
    short = _sentences(tmp_path, "four.srt", [
        (1.0, 2.0, "(one two three four) Hello."),
    ])
    long = _sentences(tmp_path, "five.srt", [
        (1.0, 2.0, "(one two three four five) Hello."),
    ])
    assert short[0]["text"] == "Hello."
    assert long[0]["text"] == "(one two three four five) Hello."


def test_italic_tag_is_removed(tmp_path):
    sentences = _sentences(tmp_path, "italic.srt", [
        (1.0, 2.0, "<i>Asked</i> to re-open."),
    ])
    assert sentences[0]["text"] == "Asked to re-open."


def test_accents_and_enie_stay(tmp_path):
    sentences = _sentences(tmp_path, "enie.srt", [
        (1.0, 3.0, "( reporter ) El niño está en el café."),
    ])
    assert sentences[0]["text"] == "El niño está en el café."


def test_empty_cue_does_not_shift_later_indices_or_times(tmp_path):
    sentences = _sentences(tmp_path, "indices.srt", [
        (1.0, 1.5, "(screams)"),
        (3.0, 5.0, "( reporter ) Asked to possibly re-open the Kyle Watson case..."),
        (6.0, 7.0, "Next line."),
    ])
    assert len(sentences) == 2
    assert sentences[0]["cue_indices"] == [1]
    assert sentences[0]["start"] == 3.0
    assert sentences[0]["end"] == 5.0
    assert sentences[1]["cue_indices"] == [2]
    assert sentences[1]["start"] == 6.0
    assert sentences[1]["end"] == 7.0


def test_saved_project_with_dirty_text_opens_unchanged(tmp_path):
    dirty = "( reporter ) Asked to possibly re-open the Kyle Watson case..."
    fingerprint = {"start": 1.0, "end": 2.0, "text": dirty}
    path = tmp_path / "dirty.anki-project.json"
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
                        "subtitles": [
                            {"index": 0, "start": 1.0, "end": 2.0, "text": dirty}
                        ],
                        "clips": [
                            {
                                "id": 1,
                                "status": "generated",
                                "text": dirty,
                                "start": 1.0,
                                "end": 2.0,
                                "subtitle_indices": [0],
                                "generation_fingerprint": fingerprint,
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
    clip = project.episodes[0].clips[0]
    subtitle = project.episodes[0].subtitles[0]
    segment = state.segments[0]

    assert clip.text == dirty
    assert subtitle.text == dirty
    assert clip.generation_fingerprint == fingerprint
    assert clip.status.value == "generated"
    assert segment["text"] == dirty
    assert segment["status"] == "exported"
    assert segment["generation_fingerprint"] == fingerprint
    assert state.cue_map[0]["text"] == dirty
