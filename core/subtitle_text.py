"""Limpieza de texto de subtítulos para comparar, sin cambiar el parseo."""

import re

from core.subtitle_parser import clean_text, normalize_case, parse_srt_blocks


_MARKUP_RE = re.compile(r"</?(?:i|b|font)\b[^>]*>", re.IGNORECASE)
_URL_LINE_RE = re.compile(r"^(?:https?://|www\.)\S+$", re.IGNORECASE)


def _is_ad_line(text: str) -> bool:
    if "opensubtitles" in text.casefold():
        return True
    return _URL_LINE_RE.match(text) is not None


def clean_subtitle_text(raw_text: str, language: str = "en") -> str:
    """Devuelve el diálogo limpio, o vacío si el bloque es un anuncio.

    Quita etiquetas i/b/font, anotaciones SDH entre () o [], colapsa
    espacios y aplica la misma normalización de mayúsculas que el clip.
    """
    if not raw_text:
        return ""
    without_tags = _MARKUP_RE.sub("", raw_text)
    cleaned = clean_text(
        without_tags,
        apply_punctuation_fix=(language != "fr"),
    )
    if not cleaned or _is_ad_line(cleaned):
        return ""
    return normalize_case(cleaned, language=language)


def load_reference_cues(path, language: str = "en") -> list[dict]:
    """Lee un SRT externo y devuelve bloques con inicio, fin y texto limpio."""
    cues = []
    for block in parse_srt_blocks(path):
        text = clean_subtitle_text(block["raw_text"], language=language)
        if not text:
            continue
        cues.append({
            "start": block["start"],
            "end": block["end"],
            "text": text,
        })
    return cues
