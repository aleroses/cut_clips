"""Lectura de .srt que no están en UTF-8 (Windows-1252 / Latin-1)."""

from core.subtitle_parser import generate_sentences, parse_srt_blocks, read_subtitle_text


SRT_BODY = """1
00:00:20,894 --> 00:00:26,261
<i>Subs Sync Checked ..by iUrop</i>

2
00:00:33,220 --> 00:00:35,520
The best food in the world
is made in France.
"""


def test_utf8_srt_still_decodes_as_utf8(tmp_path):
    path = tmp_path / "utf8.srt"
    path.write_bytes(SRT_BODY.replace("France", "caf\u00e8").encode("utf-8"))

    text, encoding = read_subtitle_text(path)
    blocks = parse_srt_blocks(path)

    assert encoding == "utf-8"
    assert "caf\u00e8" in text
    assert blocks[1]["raw_text"].endswith("caf\u00e8.")


def test_windows1252_byte_e8_does_not_crash(tmp_path):
    """0xE8 es «è» en Windows-1252 y un inicio inválido en UTF-8."""
    path = tmp_path / "ansi.srt"
    raw = SRT_BODY.replace("France", "caf\u00e8").encode("cp1252")
    assert b"\xe8" in raw
    path.write_bytes(raw)

    text, encoding = read_subtitle_text(path)
    result = generate_sentences(path)

    assert encoding == "cp1252"
    assert "caf\u00e8" in text
    assert result["encoding"] == "cp1252"
    assert any("caf\u00e8" in sentence["text"] for sentence in result["sentences"])


def test_utf8_bom_is_stripped(tmp_path):
    path = tmp_path / "bom.srt"
    path.write_bytes(b"\xef\xbb\xbf" + SRT_BODY.encode("utf-8"))

    text, encoding = read_subtitle_text(path)
    blocks = parse_srt_blocks(path)

    assert encoding == "utf-8"
    assert not text.startswith("\ufeff")
    assert blocks[0]["start"] == 20.894
