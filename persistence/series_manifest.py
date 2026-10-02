"""Numeración Line_XXXX compartida entre episodios bajo la misma carpeta de serie."""

from __future__ import annotations

import json
import os
import tempfile

MANIFEST_FILENAME = "series_manifest.json"


def series_manifest_path(series_dir: str) -> str:
    return os.path.join(series_dir, MANIFEST_FILENAME)


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


def write_series_manifest(
    series_dir: str,
    last_sequence_number: int,
    *,
    series_name: str | None = None,
) -> None:
    """Actualiza last_sequence_number (solo aumenta) con escritura atómica.

    No modifica el archivo si ya pertenece a otra series_name.
    """
    current = read_series_manifest(series_dir) or {}
    stored_name = current.get("series_name")
    if series_name and stored_name and stored_name != series_name:
        return
    os.makedirs(series_dir, exist_ok=True)
    path = series_manifest_path(series_dir)
    prev = int(current.get("last_sequence_number", 0))
    new_last = max(prev, int(last_sequence_number))
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
