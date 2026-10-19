"""Lectura de .srt en UTF-8, UTF-16, Windows-1252 y Latin-1."""

from core.subtitle_parser import generate_sentences, parse_srt_blocks, read_subtitle_text


SRT_BODY = """1
00:00:01,000 --> 00:00:02,000
El niño está en el café.
"""


def test_utf8_srt_still_decodes_as_utf8(tmp_path):
    path = tmp_path / "utf8.srt"
    path.write_bytes(SRT_BODY.encode("utf-8"))

    text, encoding = read_subtitle_text(path)
    blocks = parse_srt_blocks(path)

    assert encoding == "utf-8"
    assert "niño" in text
    assert "café" in text
    assert blocks[0]["raw_text"] == "El niño está en el café."


def test_utf8_bom_is_stripped(tmp_path):
    path = tmp_path / "bom.srt"
    path.write_bytes(b"\xef\xbb\xbf" + SRT_BODY.encode("utf-8"))

    text, encoding = read_subtitle_text(path)
    blocks = parse_srt_blocks(path)

    assert encoding == "utf-8"
    assert not text.startswith("\ufeff")
    assert "niño" in text
    assert blocks[0]["start"] == 1.0
    assert blocks[0]["raw_text"] == "El niño está en el café."


def test_utf16_bom_decodes_dialogue(tmp_path):
    path = tmp_path / "utf16.srt"
    path.write_bytes(SRT_BODY.encode("utf-16"))

    text, encoding = read_subtitle_text(path)
    blocks = parse_srt_blocks(path)

    assert encoding == "utf-16"
    assert "niño" in text
    assert "café" in text
    assert blocks[0]["raw_text"] == "El niño está en el café."


def test_windows1252_accents_do_not_crash(tmp_path):
    """0xE8 es «è» y 0xF1 es «ñ» en Windows-1252; en UTF-8 no son un carácter válido."""
    path = tmp_path / "ansi.srt"
    body = SRT_BODY.replace("café.", "cafè.")
    raw = body.encode("cp1252")
    assert b"\xe8" in raw
    assert b"\xf1" in raw
    path.write_bytes(raw)

    text, encoding = read_subtitle_text(path)
    result = generate_sentences(path)

    assert encoding == "cp1252"
    assert "niño" in text
    assert "cafè" in text
    assert any("niño" in sentence["text"] for sentence in result["sentences"])
    assert any("cafè" in sentence["text"] for sentence in result["sentences"])


def test_latin1_fallback_keeps_enie(tmp_path):
    """0x81 no existe en Windows-1252, así que la lectura cae a Latin-1."""
    path = tmp_path / "latin1.srt"
    raw = b"\x81\n\n" + SRT_BODY.encode("latin-1")
    path.write_bytes(raw)

    text, encoding = read_subtitle_text(path)
    blocks = parse_srt_blocks(path)

    assert encoding == "latin-1"
    assert "niño" in text
    assert "café" in text
    assert blocks[0]["raw_text"] == "El niño está en el café."
