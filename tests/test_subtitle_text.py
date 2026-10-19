"""Limpieza de texto de subtítulos antes de comparar."""

from core.subtitle_text import clean_subtitle_text


def test_strips_i_b_and_font_tags():
    raw = '<i>Hola</i> <b>niño</b> <font color="#fff">allí</font>'
    assert clean_subtitle_text(raw) == "Hola niño allí"


def test_strips_sdh_parentheses_and_brackets():
    assert clean_subtitle_text("Hello (reporter) there [music]") == "Hello there"


def test_drops_opensubtitles_ad():
    assert clean_subtitle_text("Subtitles by OpenSubtitles.org") == ""


def test_drops_url_only_line():
    assert clean_subtitle_text("https://example.com/subs") == ""
    assert clean_subtitle_text("www.example.com/subs") == ""


def test_upper_case_becomes_sentence_case():
    assert clean_subtitle_text("HELLO THERE.") == "Hello there."


def test_collapses_line_breaks_and_keeps_enie():
    assert clean_subtitle_text("El niño\nestá en el café.") == "El niño está en el café."


def test_mixed_case_with_enie_is_not_rewritten():
    assert clean_subtitle_text("El niño") == "El niño"
