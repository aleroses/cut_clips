#!/usr/bin/env python3
"""Recupera un TSV desde .anki-project.json incluyendo clips exported y outdated.

Uso:
    python3 tools/recover_tsv_from_project.py ruta/al/proyecto.anki-project.json

Escribe un archivo *_recovered.tsv junto al proyecto (no sobrescribe el original).
"""

from __future__ import annotations

import argparse
import os
import sys

# Raíz del repo en sys.path
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from core.clip_engine import load_translation_cache, sanitize_filename_component, write_anki_tsv
from core.naming import clip_audio_filename, clip_video_filename, format_episode_label, tsv_filename
from persistence.gui_bridge import export_sequence_number, load_gui_state_from_project
from persistence.store import load_project

GENERATED_STATUSES = frozenset({"exported", "outdated"})


def _effective_series_name(raw: str) -> str:
    safe = sanitize_filename_component((raw or "").strip() or "Series")
    return safe or "Series"


def _recovered_tsv_path(project_path: str, basename: str) -> str:
    if basename.endswith(".tsv"):
        return os.path.join(os.path.dirname(project_path), basename[:-4] + "_recovered.tsv")
    return os.path.join(os.path.dirname(project_path), basename + "_recovered.tsv")


def build_rows_from_project(project_path: str):
    project = load_project(os.path.abspath(project_path))
    state = load_gui_state_from_project(project)

    series_name = _effective_series_name(state.series_name)
    file_episode_label = format_episode_label(state.season, state.episode_num, style="compact")
    episode_title = state.episode_title or ""

    segments = list(state.segments)
    rows_full = []
    translations: dict[str, str] = {}

    for seg in segments:
        gui_status = seg.get("status")
        if gui_status not in GENERATED_STATUSES:
            continue

        seq_num = export_sequence_number(segments, seg["id"])
        video_filename = clip_video_filename(series_name, file_episode_label, seq_num)
        audio_filename = clip_audio_filename(series_name, file_episode_label, seq_num)
        text = seg.get("text", "")
        translation = seg.get("translation", "")

        rows_full.append((
            seq_num, text, video_filename, audio_filename,
            file_episode_label, episode_title, translation,
        ))
        if translation:
            translations[text] = translation

    # Respaldo: caché junto al proyecto
    cache_path = os.path.join(os.path.dirname(os.path.abspath(project_path)), "translations_cache.json")
    cache = load_translation_cache(cache_path)
    rows_for_write = []
    for seq, text, vid, aud, ep, title, seg_translation in rows_full:
        rows_for_write.append((seq, text, vid, aud, ep, title))
        if not translations.get(text):
            if seg_translation:
                translations[text] = seg_translation
            elif text in cache:
                translations[text] = cache[text]

    title_slug = episode_title or None
    basename = tsv_filename(series_name, file_episode_label, title_slug)
    out_path = _recovered_tsv_path(project_path, basename)

    return out_path, rows_for_write, translations, len(rows_for_write)


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconstruye TSV desde .anki-project.json")
    parser.add_argument("project_path", help="Ruta al archivo .anki-project.json")
    args = parser.parse_args()

    if not os.path.isfile(args.project_path):
        print(f"Error: no existe {args.project_path}", file=sys.stderr)
        return 1

    out_path, rows, translations, count = build_rows_from_project(args.project_path)
    if not rows:
        print("No hay clips exported/outdated en el proyecto.", file=sys.stderr)
        return 1

    write_anki_tsv(out_path, rows, translations)
    print(f"Recuperadas {count} fila(s) -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
