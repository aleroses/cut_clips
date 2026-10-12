"""Formato del TSV de Anki escrito por write_anki_tsv."""

import csv
import io

import pytest

from core.clip_engine import write_anki_tsv

TSV_FIELDS = (
    "id",
    "episode",
    "episode_title",
    "video",
    "video_reference",
    "video_audio",
    "english_dialogs",
    "spanish_dialogues",
    "notes",
)


def _write(tmp_path, rows, translations):
    path = tmp_path / "cards.tsv"
    write_anki_tsv(str(path), rows, translations)
    return path.read_bytes()


def _read_records(raw: bytes) -> list[list[str]]:
    reader = csv.reader(
        io.StringIO(raw.decode("utf-8"), newline=""),
        delimiter="\t",
        doublequote=True,
    )
    return list(reader)


def test_nine_fields_order_header_and_newline(tmp_path):
    video = "Example_Series_S01E01_Line_0007.webm"
    audio = "Example_Series_S01E01_Line_0007.mp3"
    raw = _write(
        tmp_path,
        [(7, "Hello there.", video, audio, "S01E01", "Pilot")],
        {"Hello there.": "Hola."},
    )
    assert raw == (
        "0007\tS01E01\tPilot\t"
        "Example_Series_S01E01_Line_0007.webm\t"
        "[sound:Example_Series_S01E01_Line_0007.webm]\t"
        "[sound:Example_Series_S01E01_Line_0007.mp3]\t"
        "Hello there.\tHola.\t\n"
    ).encode("utf-8")
    assert b"\r" not in raw
    records = _read_records(raw)
    assert len(records) == 1
    fields = records[0]
    assert len(fields) == len(TSV_FIELDS)
    assert fields == [
        "0007",
        "S01E01",
        "Pilot",
        video,
        f"[sound:{video}]",
        f"[sound:{audio}]",
        "Hello there.",
        "Hola.",
        "",
    ]
    assert not fields[0].lower().startswith("id")
    assert "english" not in raw.decode("utf-8").split("\n")[0].lower()


def test_empty_translation_and_notes_keep_nine_fields(tmp_path):
    video = "Example_Series_S01E01_Line_0001.webm"
    audio = "Example_Series_S01E01_Line_0001.mp3"
    raw = _write(
        tmp_path,
        [(1, "¿Qué tal?", video, audio, "S01E01", "Pilot")],
        {},
    )
    assert b"\r" not in raw
    assert raw.endswith(b"\n")
    fields = _read_records(raw)[0]
    assert len(fields) == 9
    assert fields[6] == "¿Qué tal?"
    assert fields[7] == ""
    assert fields[8] == ""
    assert fields[4] == f"[sound:{video}]"
    assert fields[5] == f"[sound:{audio}]"


def test_quotes_and_markup_stay_in_the_dialogue_field(tmp_path):
    text = 'She said "hello", <i>really</i>.'
    video = "clip.webm"
    audio = "clip.mp3"
    raw = _write(
        tmp_path,
        [(42, text, video, audio, "S01E01", "Pilot")],
        {text: "Ella dijo «hola»."},
    )
    fields = _read_records(raw)[0]
    assert len(fields) == 9
    assert fields[0] == "0042"
    assert fields[6] == text
    assert fields[7] == "Ella dijo «hola»."
    assert fields[8] == ""
    assert b'"She said ""hello"", <i>really</i>."' in raw


def test_tab_or_newline_inside_dialogue_still_yields_one_row_of_nine_fields(tmp_path):
    text = "Hello\tthere\nfriend"
    video = "clip.webm"
    audio = "clip.mp3"
    raw = _write(
        tmp_path,
        [(3, text, video, audio, "S01E01", "Pilot")],
        {},
    )
    records = _read_records(raw)
    assert len(records) == 1
    assert len(records[0]) == 9
    assert records[0][6] == text
    assert records[0][7] == ""
    assert records[0][8] == ""


@pytest.mark.parametrize(
    "special",
    ["Hello\tthere", "Hello\nfriend", "Hello\tthere\nfriend"],
)
def test_special_characters_round_trip_in_dialogue_translation_and_title(tmp_path, special):
    text = f"line {special}"
    translation = f"trad {special}"
    title = f"title {special}"
    video = "clip.webm"
    audio = "clip.mp3"
    raw = _write(
        tmp_path,
        [(8, text, video, audio, "S01E01", title)],
        {text: translation},
    )
    records = _read_records(raw)
    assert len(records) == 1
    assert len(records[0]) == 9
    assert records[0][0] == "0008"
    assert records[0][1] == "S01E01"
    assert records[0][2] == title
    assert records[0][3] == video
    assert records[0][4] == f"[sound:{video}]"
    assert records[0][5] == f"[sound:{audio}]"
    assert records[0][6] == text
    assert records[0][7] == translation
    assert records[0][8] == ""


def test_multiline_field_does_not_shift_the_following_record(tmp_path):
    video = "clip.webm"
    audio = "clip.mp3"
    raw = _write(
        tmp_path,
        [
            (3, "Hello\tthere\nfriend", video, audio, "S01E01", "Pilot"),
            (4, "Next line.", video, audio, "S01E01", "Second"),
        ],
        {"Next line.": "Siguiente."},
    )
    records = _read_records(raw)
    assert len(records) == 2
    assert [len(row) for row in records] == [9, 9]
    assert records[0][0] == "0003"
    assert records[0][2] == "Pilot"
    assert records[0][6] == "Hello\tthere\nfriend"
    assert records[0][7] == ""
    assert records[1] == [
        "0004",
        "S01E01",
        "Second",
        video,
        f"[sound:{video}]",
        f"[sound:{audio}]",
        "Next line.",
        "Siguiente.",
        "",
    ]
