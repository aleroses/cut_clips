"""Alineamiento one-shot entre cue_map del vídeo y texto de referencia externo."""

from __future__ import annotations

import difflib
import hashlib
import re
import string
from dataclasses import dataclass


_HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class _Word:
    original: str
    normalized: str
    cue_index: int | None = None


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub("", text)


def _normalize_token(token: str) -> str:
    cleaned = _strip_html(token).lower().strip(string.punctuation)
    return cleaned


def _tokenize_reference(text: str) -> list[_Word]:
    words: list[_Word] = []
    for raw in text.split():
        if not raw:
            continue
        normalized = _normalize_token(raw)
        if not normalized:
            continue
        words.append(_Word(original=raw, normalized=normalized))
    return words


def _tokenize_cue_map(cue_map: dict[int, dict]) -> list[_Word]:
    words: list[_Word] = []
    for cue_index in sorted(cue_map):
        cue = cue_map[cue_index]
        for raw in str(cue.get("text", "")).split():
            if not raw:
                continue
            normalized = _normalize_token(raw)
            if not normalized:
                continue
            words.append(_Word(original=raw, normalized=normalized, cue_index=cue_index))
    return words


def _compute_checksum(cue_map: dict[int, dict]) -> str:
    parts: list[str] = []
    for idx in sorted(cue_map):
        cue = cue_map[idx]
        parts.append(
            f"{idx}:{cue['start']}:{cue['end']}:{cue['text']}"
        )
    payload = "".join(parts).encode("utf-8")
    return hashlib.md5(payload).hexdigest()


def _unique_cue_indices(words: list[_Word]) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for word in words:
        if word.cue_index is None or word.cue_index in seen:
            continue
        seen.add(word.cue_index)
        ordered.append(word.cue_index)
    return ordered


def _previous_cue_index(video_words: list[_Word], pos: int) -> int | None:
    for idx in range(pos - 1, -1, -1):
        cue_index = video_words[idx].cue_index
        if cue_index is not None:
            return cue_index
    return None


def _split_reference_words_among_cues(
    ref_words: list[_Word],
    cue_indices: list[int],
) -> dict[int, list[str]]:
    assignments: dict[int, list[str]] = {cue_index: [] for cue_index in cue_indices}
    if not ref_words or not cue_indices:
        return assignments

    base, remainder = divmod(len(ref_words), len(cue_indices))
    pos = 0
    for slot, cue_index in enumerate(cue_indices):
        chunk_size = base + (1 if slot < remainder else 0)
        for word in ref_words[pos : pos + chunk_size]:
            assignments[cue_index].append(word.original)
        pos += chunk_size
    return assignments


def _append_assignments(
    target: dict[int, list[str]],
    chunk: dict[int, list[str]],
) -> None:
    for cue_index, words in chunk.items():
        target.setdefault(cue_index, []).extend(words)


def align_reference_text(cue_map: dict[int, dict], reference_text: str) -> dict:
    """Alinea texto de referencia externo contra cue_map del vídeo.

    cue_map: {cue_index: {"index", "start", "end", "text"}}
    reference_text: texto plano completo de fuente externa (sin tiempos)
    """
    checksum = _compute_checksum(cue_map) if cue_map else ""
    empty_result = {
        "checksum": checksum,
        "cue_reference_text": {},
        "differences": [],
    }

    if not cue_map or not reference_text or not reference_text.strip():
        return empty_result

    video_words = _tokenize_cue_map(cue_map)
    ref_words = _tokenize_reference(reference_text)
    if not video_words or not ref_words:
        return empty_result

    assignments: dict[int, list[str]] = {idx: [] for idx in sorted(cue_map)}
    differences: list[dict] = []

    matcher = difflib.SequenceMatcher(
        None,
        [word.normalized for word in video_words],
        [word.normalized for word in ref_words],
        autojunk=False,
    )

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        video_slice = video_words[i1:i2]
        ref_slice = ref_words[j1:j2]

        if tag == "equal":
            for offset, video_word in enumerate(video_slice):
                ref_word = ref_slice[offset]
                if video_word.cue_index is None:
                    continue
                assignments[video_word.cue_index].append(ref_word.original)
            continue

        video_text = " ".join(word.original for word in video_slice)
        reference_fragment = " ".join(word.original for word in ref_slice)
        cue_indices = _unique_cue_indices(video_slice)

        if tag == "insert":
            if cue_indices:
                _append_assignments(
                    assignments,
                    _split_reference_words_among_cues(ref_slice, cue_indices),
                )
            else:
                prev_cue = _previous_cue_index(video_words, i1)
                if prev_cue is not None:
                    assignments[prev_cue].extend(word.original for word in ref_slice)
                else:
                    cue_indices = []
        elif tag in ("replace", "delete"):
            if ref_slice and cue_indices:
                _append_assignments(
                    assignments,
                    _split_reference_words_among_cues(ref_slice, cue_indices),
                )
            elif ref_slice and not cue_indices:
                prev_cue = _previous_cue_index(video_words, i1)
                if prev_cue is not None:
                    assignments[prev_cue].extend(word.original for word in ref_slice)

        differences.append(
            {
                "video_text": video_text,
                "reference_text": reference_fragment,
                "cue_indices": cue_indices,
            }
        )

    cue_reference_text = {
        cue_index: " ".join(assignments.get(cue_index, [])).strip()
        for cue_index in sorted(cue_map)
    }

    return {
        "checksum": checksum,
        "cue_reference_text": cue_reference_text,
        "differences": differences,
    }


if __name__ == "__main__":
    sample_cue_map = {
        0: {
            "index": 0,
            "start": 0.0,
            "end": 1.5,
            "text": "Hi there",
        },
        1: {
            "index": 1,
            "start": 1.5,
            "end": 3.0,
            "text": "How <i>are</i> you",
        },
        2: {
            "index": 2,
            "start": 3.0,
            "end": 4.5,
            "text": "Fine thanks",
        },
        3: {
            "index": 3,
            "start": 4.5,
            "end": 6.0,
            "text": "Goodbye",
        },
    }
    sample_reference = "High there How are you Fine thanks Goodbye"

    result = align_reference_text(sample_cue_map, sample_reference)

    print("checksum:", result["checksum"])
    print("\ncue_reference_text:")
    for cue_index, text in sorted(result["cue_reference_text"].items()):
        print(f"  [{cue_index}] {text!r}")

    print("\ndifferences:")
    for diff in result["differences"]:
        print(
            f"  cues={diff['cue_indices']} | "
            f"video={diff['video_text']!r} | ref={diff['reference_text']!r}"
        )
