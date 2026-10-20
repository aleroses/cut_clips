"""SRT externo como bloques con tiempo y texto limpio."""

from persistence.gui_bridge import reference_alignment_from_dict
from core.subtitle_text import (
    REFERENCE_MATCH_TOLERANCE_SEC,
    align_reference_to_clip,
    load_reference_cues,
    reference_differences,
    reference_text_for_range,
    reread_reference_cues,
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


def test_sdh_labels_are_not_differences():
    cue_map = {
        0: {
            "start": 1.0,
            "end": 2.0,
            "text": "Hello (reporter) (male) (radio) (screams) there",
        },
    }
    cues = [{"start": 1.0, "end": 2.0, "text": "Hello there"}]
    diffs = reference_differences(cue_map, cues)
    blob = " ".join(
        f"{item['video_text']} {item['reference_text']}" for item in diffs
    ).casefold()
    for word in ("reporter", "male", "radio", "screams"):
        assert word not in blob
    assert diffs == []


def test_extra_external_words_are_not_a_difference():
    cue_map = {0: {"start": 1.0, "end": 2.0, "text": "Hello there"}}
    cues = [{"start": 1.0, "end": 2.0, "text": "Well hello there friend"}]
    assert reference_differences(cue_map, cues) == []


def test_one_different_word_is_a_difference():
    cue_map = {0: {"start": 1.0, "end": 2.0, "text": "Do the things we do"}}
    cues = [{"start": 1.0, "end": 2.0, "text": "noise Do the stuff we do tail"}]
    assert reference_differences(cue_map, cues) == [{
        "video_text": "Do the things we do",
        "reference_text": "Do the stuff we do",
        "cue_indices": [0],
    }]


def test_missing_word_is_a_difference():
    clips = [{
        "start": 1.0,
        "end": 2.0,
        "text": "Hello there friend",
        "cue_indices": [4, 5],
    }]
    cues = [{"start": 1.0, "end": 2.0, "text": "Hello there"}]
    assert reference_differences(clips, cues) == [{
        "video_text": "Hello there friend",
        "reference_text": "Hello there",
        "cue_indices": [4, 5],
    }]


def test_deleted_clip_is_not_a_difference():
    clips = [{
        "start": 1.0,
        "end": 2.0,
        "text": "Hello there friend",
        "cue_indices": [1],
        "status": "deleted",
    }]
    cues = [{"start": 1.0, "end": 2.0, "text": "Hello there"}]
    assert reference_differences(clips, cues) == []


def test_real_dialogue_change_is_a_difference():
    cue_map = {0: {"start": 1.0, "end": 2.0, "text": "Hello there"}}
    cues = [{"start": 1.0, "end": 2.0, "text": "Goodbye there"}]
    assert reference_differences(cue_map, cues) == [{
        "video_text": "Hello there",
        "reference_text": "Goodbye there",
        "cue_indices": [0],
    }]


def test_case_and_loose_punctuation_are_not_differences():
    cue_map = {0: {"start": 1.0, "end": 2.0, "text": "Hello, there!"}}
    cues = [{"start": 1.0, "end": 2.0, "text": "hello there"}]
    assert reference_differences(cue_map, cues) == []


def test_old_reference_map_without_cues_still_loads():
    restored = reference_alignment_from_dict({
        "checksum": "abc",
        "cue_reference_text": {"1": "00:00:01,000 dirty"},
        "differences": [{"cue_indices": [1], "video_text": "a", "reference_text": "b"}],
    })
    assert "reference_cues" not in restored
    assert restored["cue_reference_text"][1] == "00:00:01,000 dirty"


def test_reference_cues_are_an_optional_field():
    restored = reference_alignment_from_dict({
        "checksum": "abc",
        "cue_reference_text": {},
        "differences": [],
        "reference_cues": [{"start": "1.5", "end": 2, "text": "Hola"}],
    })
    assert restored["reference_cues"] == [{"start": 1.5, "end": 2.0, "text": "Hola"}]


def test_invalid_reference_cues_are_ignored():
    restored = reference_alignment_from_dict({
        "cue_reference_text": {"0": "viejo"},
        "reference_cues": "nope",
    })
    assert "reference_cues" not in restored
    assert restored["cue_reference_text"][0] == "viejo"


SPAWN_CLIP = (
    "Do the things we do in this life screw you in the one "
    "that comes after? I think so."
)
SPAWN_EXTERNAL = (
    "Strike a match and a fire starts. Do the things we do in this life "
    "Screw you in the one that comes after? I think so. "
    "Spawn's learning that little lesson too."
)


def test_aligns_the_spawn_sentence():
    cues = [{"start": 1.0, "end": 5.0, "text": SPAWN_EXTERNAL}]
    assert align_reference_to_clip(SPAWN_CLIP, cues, 1.0, 5.0) == SPAWN_CLIP


def test_trims_text_before_and_after_the_clip():
    clip = "Hello there friend."
    cues = [{"start": 1.0, "end": 2.0, "text": "Well hello there friend. today"}]
    assert align_reference_to_clip(clip, cues, 1.0, 2.0) == "Hello there friend."


def test_one_different_word_stays_inside_the_trim():
    clip = "Do the things we do"
    cues = [{"start": 1.0, "end": 2.0, "text": "noise Do the stuff we do tail"}]
    assert align_reference_to_clip(clip, cues, 1.0, 2.0) == "Do the stuff we do"


def test_single_word_clip():
    cues = [{"start": 1.0, "end": 2.0, "text": "Well hello there."}]
    assert align_reference_to_clip("Hello", cues, 1.0, 2.0) == "Hello"


def test_align_without_overlap_is_empty():
    cues = [{"start": 10.0, "end": 11.0, "text": "Hello there"}]
    assert align_reference_to_clip("Hello there", cues, 1.0, 2.0) == ""


def test_align_keeps_accents_and_enie():
    clip = "El niño está aquí."
    cues = [{"start": 1.0, "end": 2.0, "text": "Mira, el niño está aquí. ahora"}]
    assert align_reference_to_clip(clip, cues, 1.0, 2.0) == "El niño está aquí."


def test_align_keeps_apostrophes():
    clip = "You're hearing Spawn's lesson."
    cues = [{
        "start": 1.0,
        "end": 2.0,
        "text": "Well you're hearing Spawn's lesson. now",
    }]
    assert align_reference_to_clip(clip, cues, 1.0, 2.0) == (
        "You're hearing spawn's lesson."
    )
    curly = [{"start": 1.0, "end": 2.0, "text": "You\u2019re fine. today"}]
    assert align_reference_to_clip("You're fine.", curly, 1.0, 2.0) == (
        "You\u2019re fine."
    )


def test_neighbor_block_supplies_the_rest_of_the_clip():
    clip = "Hello there"
    cues = [
        {"start": 0.0, "end": 0.4, "text": "Well"},
        {"start": 1.0, "end": 2.0, "text": "hello"},
        {"start": 2.5, "end": 3.0, "text": "there now"},
    ]
    assert align_reference_to_clip(clip, cues, 1.0, 2.0) == "Hello there"


def test_low_match_returns_the_time_window_without_neighbors():
    clip = "alpha beta gamma delta"
    cues = [
        {"start": 0.0, "end": 0.4, "text": "before"},
        {"start": 1.0, "end": 2.0, "text": "alpha other words here"},
        {"start": 3.0, "end": 4.0, "text": "after"},
    ]
    assert align_reference_to_clip(clip, cues, 1.0, 2.0) == "alpha other words here"


def test_reference_path_is_optional():
    restored = reference_alignment_from_dict({
        "checksum": "abc",
        "cue_reference_text": {},
        "differences": [],
        "reference_path": "/tmp/ext.srt",
    })
    assert restored["reference_path"] == "/tmp/ext.srt"


def test_invalid_reference_path_is_ignored():
    restored = reference_alignment_from_dict({
        "cue_reference_text": {"0": "viejo"},
        "reference_path": 12,
    })
    assert "reference_path" not in restored
    assert restored["cue_reference_text"][0] == "viejo"


def test_old_dirty_text_is_kept_when_there_is_no_path():
    alignment = {
        "cue_reference_text": {1: "00:00:01,000 dirty"},
        "differences": [],
    }
    assert reread_reference_cues(alignment) is None
    assert alignment["cue_reference_text"][1] == "00:00:01,000 dirty"
    assert "reference_cues" not in alignment


def test_missing_srt_keeps_saved_cues(tmp_path):
    missing = tmp_path / "gone.srt"
    alignment = {
        "reference_path": str(missing),
        "reference_cues": [{"start": 1.0, "end": 2.0, "text": "guardado"}],
        "cue_reference_text": {0: "00:00:01,000 dirty"},
    }
    assert reread_reference_cues(alignment) == str(missing)
    assert alignment["reference_cues"] == [{
        "start": 1.0,
        "end": 2.0,
        "text": "guardado",
    }]
    assert alignment["cue_reference_text"][0] == "00:00:01,000 dirty"


def test_reread_loads_cleaned_cues(tmp_path):
    path = tmp_path / "ref.srt"
    path.write_bytes(SRT_BODY.encode("utf-8"))
    alignment = {
        "reference_path": str(path),
        "reference_cues": [{"start": 9.0, "end": 9.5, "text": "viejo"}],
    }
    assert reread_reference_cues(alignment) is None
    assert alignment["reference_cues"] == [{
        "start": 1.0,
        "end": 2.0,
        "text": "El niño está en el café.",
    }]


def test_reread_oserror_keeps_saved_cues(tmp_path, monkeypatch):
    path = tmp_path / "ref.srt"
    path.write_text("x", encoding="utf-8")
    alignment = {
        "reference_path": str(path),
        "reference_cues": [{"start": 1.0, "end": 2.0, "text": "guardado"}],
    }

    def boom(_path, language="en"):
        raise OSError("nope")

    monkeypatch.setattr("core.subtitle_text.load_reference_cues", boom)
    assert reread_reference_cues(alignment) == str(path)
    assert alignment["reference_cues"][0]["text"] == "guardado"
