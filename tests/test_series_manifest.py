"""series_manifest.json: lectura, tope de secuencia y nombre de serie."""

import json
from pathlib import Path

from persistence.series_manifest import (
    read_series_manifest,
    series_manifest_path,
    write_series_manifest,
)


def test_create_and_read_manifest(tmp_path):
    series_dir = tmp_path / "Example_Series"
    assert read_series_manifest(str(series_dir)) is None

    write_series_manifest(str(series_dir), 4, series_name="Example_Series")
    data = read_series_manifest(str(series_dir), expected_series_name="Example_Series")
    assert data == {
        "last_sequence_number": 4,
        "series_name": "Example_Series",
    }
    names = [path.name for path in series_dir.iterdir()]
    assert names == ["series_manifest.json"]


def test_last_sequence_number_does_not_decrease(tmp_path):
    series_dir = tmp_path / "Example_Series"
    write_series_manifest(str(series_dir), 10, series_name="Example_Series")
    write_series_manifest(str(series_dir), 3, series_name="Example_Series")
    data = read_series_manifest(str(series_dir))
    assert data["last_sequence_number"] == 10
    assert data["series_name"] == "Example_Series"


def test_other_series_name_does_not_overwrite_manifest(tmp_path):
    series_dir = tmp_path / "shared"
    write_series_manifest(str(series_dir), 4, series_name="Alpha")
    manifest_path = series_manifest_path(str(series_dir))
    original = json.loads(Path(manifest_path).read_text(encoding="utf-8"))

    write_series_manifest(str(series_dir), 9, series_name="Beta")

    on_disk = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    assert on_disk == original
    assert on_disk["last_sequence_number"] == 4
    assert on_disk["series_name"] == "Alpha"
    assert read_series_manifest(str(series_dir), expected_series_name="Beta") is None
    assert read_series_manifest(str(series_dir), expected_series_name="Alpha")["last_sequence_number"] == 4
