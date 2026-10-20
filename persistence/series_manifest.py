"""Numeración Line_XXXX compartida entre episodios bajo la misma carpeta de serie."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile

MANIFEST_FILENAME = "series_manifest.json"
_CLIP_RE = re.compile(
    r"_S(\d{2})E(\d{2})_Line_(\d+)\.(?:webm|mp3)$",
    re.IGNORECASE,
)


def series_manifest_path(series_dir: str) -> str:
    return os.path.join(series_dir, MANIFEST_FILENAME)


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def project_root() -> str:
    """Raíz del repositorio. Los tests pueden sustituirla."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def manifest_dir_for_episode(episode_dir: str, media_kind: str) -> str | None:
    """Carpeta del manifiesto, o None si este episodio no debe usarlo.

    Una película no tiene capítulo siguiente. Una serie deja el archivo
    en la carpeta padre del episodio. Si esa carpeta se llama data, o si
    el padre es la raíz del proyecto, el archivo se queda en el episodio.
    Nunca se escribe en la raíz del proyecto.
    """
    if media_kind == "movie":
        return None
    episode_dir = os.path.abspath(episode_dir)
    if _norm(episode_dir) == _norm(project_root()):
        return None
    parent = os.path.dirname(episode_dir)
    if not parent or _norm(parent) == _norm(episode_dir):
        return None
    named_data = os.path.basename(episode_dir).lower() == "data"
    parent_is_root = _norm(parent) == _norm(project_root())
    if named_data or parent_is_root:
        return episode_dir
    return parent


def read_series_manifest(
    series_dir: str,
    *,
    expected_series_name: str | None = None,
) -> dict | None:
    """Lee manifest en series_dir. None si no existe o series_name no coincide."""
    path = series_manifest_path(series_dir)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    stored_name = data.get("series_name")
    if expected_series_name and stored_name:
        if stored_name != expected_series_name:
            return None
    return data


def _output_dirs(series_dir: str) -> list[str]:
    """output_files/ de cada capítulo, o el de la propia carpeta si no hay capítulos."""
    series_dir = os.path.abspath(series_dir)
    if not os.path.isdir(series_dir):
        return []
    found: list[str] = []
    for name in sorted(os.listdir(series_dir)):
        output_dir = os.path.join(series_dir, name, "output_files")
        if os.path.isdir(output_dir):
            found.append(output_dir)
    if found:
        return found
    direct = os.path.join(series_dir, "output_files")
    if os.path.isdir(direct):
        return [direct]
    return []


def _iter_clip_lines(output_dir: str, series_name: str):
    prefix = series_name + "_"
    if not os.path.isdir(output_dir):
        return
    for filename in os.listdir(output_dir):
        if not filename.startswith(prefix):
            continue
        match = _CLIP_RE.search(filename)
        if match is None:
            continue
        yield int(match.group(1)), int(match.group(2)), int(match.group(3))


def highest_prior_line(
    series_dir: str,
    series_name: str,
    season: int,
    episode: int,
) -> int | None:
    """Mayor Line_ de episodios anteriores, o None si no hay clips."""
    current = (int(season), int(episode))
    best: int | None = None
    for output_dir in _output_dirs(series_dir):
        for clip_season, clip_episode, line in _iter_clip_lines(output_dir, series_name):
            if (clip_season, clip_episode) >= current:
                continue
            if best is None or line > best:
                best = line
    return best


def episode_output_has_clips(
    output_dir: str,
    series_name: str,
    season: int,
    episode: int,
) -> bool:
    """True si output_dir ya tiene un clip de este episodio."""
    current = (int(season), int(episode))
    for clip_season, clip_episode, _line in _iter_clip_lines(output_dir, series_name):
        if (clip_season, clip_episode) == current:
            return True
    return False


def stale_manifest_bounds(
    *,
    media_kind: str,
    manifest_last: int | None,
    prior_line: int | None,
    episode_has_clips: bool,
) -> tuple[int, int] | None:
    """(N, M) si hay que preguntar. None si no corresponde avisar."""
    if media_kind == "movie" or episode_has_clips:
        return None
    if manifest_last is None or prior_line is None:
        return None
    manifest_last = int(manifest_last)
    prior_line = int(prior_line)
    if manifest_last <= prior_line:
        return None
    return manifest_last, prior_line


def confirm_lower_series_manifest(
    series_dir: str,
    last_sequence_number: int,
    *,
    series_name: str | None = None,
    accept: bool,
) -> bool:
    """Con accept, guarda .bak y escribe el valor aunque sea menor.

    Sin accept no crea ni modifica ningún archivo.
    """
    if not accept:
        return False
    path = series_manifest_path(series_dir)
    if os.path.isfile(path):
        shutil.copy2(path, path + ".bak")
    write_series_manifest(
        series_dir,
        last_sequence_number,
        series_name=series_name,
        allow_decrease=True,
    )
    return True


def write_series_manifest(
    series_dir: str,
    last_sequence_number: int,
    *,
    series_name: str | None = None,
    allow_decrease: bool = False,
) -> None:
    """Actualiza last_sequence_number con escritura atómica.

    Por defecto solo aumenta. allow_decrease escribe el valor pedido.
    No modifica el archivo si ya pertenece a otra series_name.
    """
    current = read_series_manifest(series_dir) or {}
    stored_name = current.get("series_name")
    if series_name and stored_name and stored_name != series_name:
        return
    os.makedirs(series_dir, exist_ok=True)
    path = series_manifest_path(series_dir)
    prev = int(current.get("last_sequence_number", 0))
    requested = int(last_sequence_number)
    new_last = requested if allow_decrease else max(prev, requested)
    payload: dict = {"last_sequence_number": new_last}
    if series_name:
        payload["series_name"] = series_name
    elif current.get("series_name"):
        payload["series_name"] = current["series_name"]
    fd, tmp_path = tempfile.mkstemp(
        dir=series_dir, prefix=".series_manifest_", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
