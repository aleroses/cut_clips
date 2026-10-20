"""Limpieza de texto de subtítulos para comparar, sin cambiar el parseo."""

import difflib
import re
import unicodedata

from core.subtitle_parser import (
    apply_sentence_case,
    clean_text,
    normalize_case,
    parse_srt_blocks,
)


_MARKUP_RE = re.compile(r"</?(?:i|b|font)\b[^>]*>", re.IGNORECASE)
_URL_LINE_RE = re.compile(r"^(?:https?://|www\.)\S+$", re.IGNORECASE)

REFERENCE_MATCH_TOLERANCE_SEC = 0.5
_REFERENCE_MATCH_RATIO = 0.5
_APOSTROPHES = frozenset({"'", "\u2019"})


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


def _alignment_tokens(text: str) -> list[tuple[str, str]]:
    """Pares (original, clave). La clave va en minúsculas y sin puntuación.

    El apóstrofe se queda, para que you're y spawn's sean una sola palabra.
    """
    tokens = []
    for raw in str(text or "").split():
        key_chars = []
        for char in raw.casefold():
            if char in _APOSTROPHES:
                key_chars.append("'")
                continue
            if unicodedata.category(char).startswith("P"):
                continue
            key_chars.append(char)
        key = "".join(key_chars)
        if not key:
            continue
        tokens.append((raw, key))
    return tokens


def _candidate_cues(cues, start: float, end: float, tolerance: float) -> list[dict]:
    """Bloques que solapan [start - tol, end + tol), más un vecino a cada lado.

    Sin solape no se traen vecinos: la lista queda vacía.
    """
    window_start = start - tolerance
    window_end = end + tolerance
    overlapping = []
    for index, cue in enumerate(cues):
        cue_start = float(cue["start"])
        cue_end = float(cue["end"])
        if cue_start < window_end and cue_end > window_start:
            overlapping.append(index)
    if not overlapping:
        return []
    first = overlapping[0]
    last = overlapping[-1]
    begin = 0 if first == 0 else first - 1
    end_index = min(len(cues), last + 2)
    return list(cues[begin:end_index])


def align_reference_to_clip(
    clip_text: str,
    cues,
    start: float,
    end: float,
    language: str = "en",
    tolerance: float = REFERENCE_MATCH_TOLERANCE_SEC,
) -> str:
    """Recorta el texto externo al diálogo del clip.

    Si coinciden menos de la mitad de las palabras del clip, devuelve el
    texto por tiempo, sin vecinos y sin recortar.
    """
    candidates = _candidate_cues(cues, start, end, tolerance)
    if not candidates:
        return ""

    external_tokens = []
    for cue in candidates:
        external_tokens.extend(_alignment_tokens(str(cue.get("text") or "")))
    clip_tokens = _alignment_tokens(clip_text)
    if not clip_tokens or not external_tokens:
        return reference_text_for_range(cues, start, end, tolerance)

    matcher = difflib.SequenceMatcher(
        None,
        [key for _original, key in external_tokens],
        [key for _original, key in clip_tokens],
        autojunk=False,
    )
    blocks = [block for block in matcher.get_matching_blocks() if block.size]
    matched = sum(block.size for block in blocks)
    if not blocks or matched / len(clip_tokens) < _REFERENCE_MATCH_RATIO:
        return reference_text_for_range(cues, start, end, tolerance)

    first = blocks[0]
    last = blocks[-1]
    start_index = max(0, first.a - first.b)
    unmatched_suffix = len(clip_tokens) - (last.b + last.size)
    end_index = min(len(external_tokens), last.a + last.size + unmatched_suffix)
    words = [original for original, _key in external_tokens[start_index:end_index]]
    return apply_sentence_case(" ".join(words), language=language)


def _fold_for_compare(text: str) -> str:
    """Minúsculas y sin puntuación, para decidir si dos textos dicen lo mismo."""
    kept = []
    for char in text.casefold():
        if unicodedata.category(char).startswith("P"):
            continue
        kept.append(char)
    return " ".join("".join(kept).split())


def _iter_reference_clips(clips):
    """Cada clip con su texto, intervalo e índices. Un mapa de cues también vale."""
    if isinstance(clips, dict):
        items = (
            (int(key), clips[key])
            for key in sorted(clips, key=lambda key: int(key))
        )
        for cue_index, cue in items:
            if cue.get("status") == "deleted":
                continue
            stored = cue.get("cue_indices")
            indices = [cue_index] if not stored else [int(index) for index in stored]
            yield {
                "text": cue.get("text") or "",
                "start": float(cue["start"]),
                "end": float(cue["end"]),
                "cue_indices": indices,
            }
        return
    for clip in clips:
        if clip.get("status") == "deleted":
            continue
        yield {
            "text": clip.get("text") or "",
            "start": float(clip["start"]),
            "end": float(clip["end"]),
            "cue_indices": [int(index) for index in (clip.get("cue_indices") or [])],
        }


def reference_differences(
    clips,
    reference_cues: list[dict],
    language: str = "en",
) -> list[dict]:
    """Diferencias entre el texto de cada clip y el texto externo alineado."""
    differences = []
    for clip in _iter_reference_clips(clips):
        video_text = clean_subtitle_text(str(clip["text"] or ""), language=language)
        reference_text = align_reference_to_clip(
            video_text,
            reference_cues,
            clip["start"],
            clip["end"],
            language=language,
        )
        if _fold_for_compare(video_text) == _fold_for_compare(reference_text):
            continue
        differences.append({
            "video_text": video_text,
            "reference_text": reference_text,
            "cue_indices": clip["cue_indices"],
        })
    return differences
