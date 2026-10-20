#!/usr/bin/env python3
"""Reconstruye series_manifest.json a partir de los clips ya generados.

Por defecto no escribe nada. Muestra el JSON que escribiría.
Solo crea o reemplaza el archivo con --apply.

Ejemplo:
    python3 tools/rebuild_series_manifest.py --series-dir /ruta/Spawn_S01 --series-name Todd_McFarlanes_Spawn
    python3 tools/rebuild_series_manifest.py --series-dir /ruta/Spawn_S01 --series-name Todd_McFarlanes_Spawn --apply
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from persistence import series_manifest as series_manifest_api
from persistence.series_manifest import (
    read_series_manifest,
    series_manifest_path,
    write_series_manifest,
)

_CLIP_RE = re.compile(r"_S(\d{2})E(\d{2})_Line_(\d+)\.(?:webm|mp3)$", re.IGNORECASE)


def episode_dirs(series_dir: str) -> list[str]:
    """Capítulos con output_files/ bajo series_dir.

    Si no hay subcarpetas así, y la propia carpeta tiene output_files/,
    esa carpeta es el episodio.
    """
    series_dir = os.path.abspath(series_dir)
    if not os.path.isdir(series_dir):
        return []
    found: list[str] = []
    for name in sorted(os.listdir(series_dir)):
        episode_dir = os.path.join(series_dir, name)
        if os.path.isdir(os.path.join(episode_dir, "output_files")):
            found.append(episode_dir)
    if found:
        return found
    if os.path.isdir(os.path.join(series_dir, "output_files")):
        return [series_dir]
    return []


def resolve_manifest_dir(series_dir: str) -> str | None:
    """Carpeta donde escribir el manifiesto, o None si no hay un solo sitio seguro.

    Usa manifest_dir_for_episode. No devuelve la raíz del proyecto.
    """
    episodes = episode_dirs(series_dir)
    if not episodes:
        return None
    chosen: list[str] = []
    root = os.path.normcase(
        os.path.normpath(os.path.abspath(series_manifest_api.project_root()))
    )
    for episode in episodes:
        dest = series_manifest_api.manifest_dir_for_episode(episode, "series")
        if not dest:
            return None
        dest_abs = os.path.abspath(dest)
        if os.path.normcase(os.path.normpath(dest_abs)) == root:
            return None
        chosen.append(dest_abs)
    first = chosen[0]
    first_norm = os.path.normcase(os.path.normpath(first))
    for path in chosen[1:]:
        if os.path.normcase(os.path.normpath(path)) != first_norm:
            return None
    return first


def scan_episode_lines(series_dir: str, series_name: str) -> dict[tuple[int, int], int]:
    """Mayor Line_ de cada capítulo que tenga clips en output_files/."""
    found: dict[tuple[int, int], int] = {}
    prefix = series_name + "_"
    for episode_dir in episode_dirs(series_dir):
        output_dir = os.path.join(episode_dir, "output_files")
        for filename in os.listdir(output_dir):
            if not filename.startswith(prefix):
                continue
            match = _CLIP_RE.search(filename)
            if match is None:
                continue
            key = (int(match.group(1)), int(match.group(2)))
            line = int(match.group(3))
            found[key] = max(found.get(key, 0), line)
    return found


def resolve_last_sequence(
    found: dict[tuple[int, int], int],
    *,
    last_season: int | None = None,
    last_episode: int | None = None,
    last_line: int | None = None,
) -> int:
    """Elige last_sequence_number. Lanza ValueError si no hay datos suficientes."""
    if (last_season is None) != (last_episode is None):
        raise ValueError("Hacen falta --last-season y --last-episode juntos.")
    if last_season is not None and last_episode is not None:
        key = (last_season, last_episode)
        if key in found:
            return found[key]
        if last_line is not None:
            return last_line
        label = f"S{last_season:02d}E{last_episode:02d}"
        raise ValueError(
            f"No hay clips de {label} y falta --last-line. No se inventó un número."
        )
    if found:
        highest = max(found)
        return found[highest]
    if last_line is not None:
        return last_line
    raise ValueError(
        "No hay clips que escanear y falta --last-line. No se inventó un número."
    )


def manifest_payload(last_sequence_number: int, series_name: str) -> dict:
    return {
        "last_sequence_number": int(last_sequence_number),
        "series_name": series_name,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--series-dir", required=True, help="Carpeta donde vive el manifiesto")
    parser.add_argument("--series-name", required=True, help="series_name que se guarda en el JSON")
    parser.add_argument("--last-season", type=int, default=None)
    parser.add_argument("--last-episode", type=int, default=None)
    parser.add_argument(
        "--last-line",
        type=int,
        default=None,
        help="Respaldo manual si ese capítulo no tiene clips",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra el JSON y no escribe. Es el comportamiento por defecto.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Escribe el manifiesto. Sin esta opción no se crea ningún archivo.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Permite reemplazar un manifiesto existente. Guarda una copia .bak.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    series_dir = os.path.abspath(args.series_dir)
    try:
        found = scan_episode_lines(series_dir, args.series_name)
        last_sequence = resolve_last_sequence(
            found,
            last_season=args.last_season,
            last_episode=args.last_episode,
            last_line=args.last_line,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    manifest_dir = resolve_manifest_dir(series_dir)
    if manifest_dir is None:
        print(
            "No se escribió el manifiesto. Esa ruta caería en la raíz del proyecto "
            "o los episodios no comparten carpeta.",
            file=sys.stderr,
        )
        return 1

    path = series_manifest_path(manifest_dir)
    payload = manifest_payload(last_sequence, args.series_name)
    current = read_series_manifest(manifest_dir)
    stored_name = (current or {}).get("series_name")
    if stored_name and stored_name != args.series_name:
        print(
            f"El manifiesto ya pertenece a {stored_name}. No se modificó.",
            file=sys.stderr,
        )
        return 1

    exists = os.path.isfile(path)
    if exists and not args.force:
        print(f"El manifiesto ya existe: {path}", file=sys.stderr)
        print("No se sobrescribió. Pasa --force para reemplazarlo.", file=sys.stderr)
        return 1

    print(path)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if not args.apply:
        print("Dry-run: no se escribió ningún archivo.")
        return 0

    if exists:
        bak_path = path + ".bak"
        shutil.copy2(path, bak_path)
        print(f"Copia de seguridad: {bak_path}")

    previous = int((current or {}).get("last_sequence_number", 0))
    write_series_manifest(
        manifest_dir,
        last_sequence,
        series_name=args.series_name,
    )
    written = read_series_manifest(manifest_dir) or {}
    kept = int(written.get("last_sequence_number", last_sequence))
    if kept > last_sequence:
        print(
            f"Se conservó el valor más alto ya guardado: {kept} "
            f"(el escaneo pedía {last_sequence})."
        )
    elif previous and previous > last_sequence:
        print(f"Se conservó el valor más alto ya guardado: {kept}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
