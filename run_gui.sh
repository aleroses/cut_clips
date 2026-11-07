#!/usr/bin/env bash
# Launch the cut_clips GUI using the project virtualenv.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Missing .venv. From the project root run:" >&2
  echo "  python3 -m venv .venv" >&2
  echo "  .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  echo "FFmpeg/ffprobe not found. Install with:" >&2
  echo "  sudo apt install ffmpeg" >&2
  exit 1
fi

exec "$PY" "$ROOT/gui_app.py" "$@"
