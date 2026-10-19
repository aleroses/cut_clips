"""Limpieza de texto de subtítulos para comparar, sin cambiar el parseo."""

import re
import unicodedata

from core.subtitle_parser import clean_text, normalize_case, parse_srt_blocks


_MARKUP_RE = re.compile(r"</?(?:i|b|font)\b[^>]*>", re.IGNORECASE)
_URL_LINE_RE = re.compile(r"^(?:https?://|www\.)\S+$", re.IGNORECASE)

REFERENCE_MATCH_TOLERANCE_SEC = 0.5


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


def reference_text_for_range(
    cues,
    start: float,
    end: float,
    tolerance: float = REFERENCE_MATCH_TOLERANCE_SEC,
) -> str:
    """Texto limpio de los bloques que solapan [start - tol, end + tol]."""
    window_start = start - tolerance
    window_end = end + tolerance
    parts = []
    for cue in cues:
        cue_start = float(cue["start"])
        cue_end = float(cue["end"])
        if cue_start <= window_end and cue_end >= window_start:
            text = str(cue.get("text") or "").strip()
            if text:
                parts.append(text)
    return " ".join(parts)


def _fold_for_compare(text: str) -> str:
    """Minúsculas y sin puntuación, para decidir si dos textos dicen lo mismo."""
    kept = []
    for char in text.casefold():
        if unicodedata.category(char).startswith("P"):
            continue
        kept.append(char)
    return " ".join("".join(kept).split())


def reference_differences(
    cue_map: dict,
    reference_cues: list[dict],
    language: str = "en",
) -> list[dict]:
    """Diferencias entre cada cue del vídeo y el texto externo que lo solapa."""
    differences = []
    for cue_index in sorted(cue_map, key=lambda key: int(key)):
        cue = cue_map[cue_index]
        video_text = clean_subtitle_text(str(cue.get("text") or ""), language=language)
        reference_text = reference_text_for_range(
            reference_cues,
            float(cue["start"]),
            float(cue["end"]),
        )
        if _fold_for_compare(video_text) == _fold_for_compare(reference_text):
            continue
        differences.append({
            "video_text": video_text,
            "reference_text": reference_text,
            "cue_indices": [int(cue_index)],
        })
    return differences
