# cut_clips
A tool to cut video clips, translate subtitles, and generate TSV files ready for Anki import.

`cut_clips` is designed to streamline language learning through audiovisual content. The tool processes video episodes to:

- Extract video and/or audio clips from subtitles.
- Manually adjust timestamps and subtitle text before generating the clips.
- Automatically translate subtitles into the target language using the DeepL API.
- Generate a `.tsv` file compatible with Anki imports.
- Maintain sequential clip numbering across multiple episodes.

This makes it possible to turn an entire video episode into Anki study material with just a few steps.

## Pendiente para Windows

La rama `debian` tiene cambios que todavía no están en la rama de Windows. La lista, con commits y archivos, está en [docs/PENDING_WINDOWS.md](docs/PENDING_WINDOWS.md).

## Key Features

- Precise video and audio clip cutting.
- `.srt` subtitle processing.
- Manual timestamp and subtitle text adjustment through a `.csv` file.
- Automatic subtitle translation using the DeepL API.
- Anki-compatible TSV generation.
- Sequential clip numbering across episodes.
- Translation caching to avoid translating the same content repeatedly.

## Requirements

You need the following:

- Python 3.10+ (3.12 on Pop!_OS / Ubuntu 24.04 is fine)
- FFmpeg and ffprobe
- Anki for importing the generated `.tsv` file

For the GUI (Debian / Ubuntu / Pop!_OS):

- `libmpv2` (or `libmpv1` on older releases) — embedded preview
- `libxcb-cursor0` — required by Qt 6.5+ for the `xcb` platform plugin (needed on Wayland/XWayland)

Optional translation (CLI `--translate` or GUI export):

- **DeepL** (`deepl`) — `DEEPL_API_KEY` or key saved in the GUI
- **Gemini** (`google-genai`) — `GEMINI_API_KEY` or key saved in the GUI

## Installation (Debian / Ubuntu / Pop!_OS)

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv ffmpeg libmpv2 libxcb-cursor0

cd /path/to/cut_clips
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

`requirements.txt` installs `deepl`, `google-genai`, `PySide6`, and `python-mpv`.

> Prefer a virtual environment. Installing with system `pip … --break-system-packages` works but mixes project packages into the OS Python.

Quick GUI start after setup, from the project directory:

```bash
./run_gui.sh
# or: .venv/bin/python gui_app.py
```

On Pop!_OS a double-click opens `run_gui.sh` in an editor. From the project folder, `./run_gui.sh` opens the GUI. Dragging `run_gui.sh` onto a terminal does the same.

## Basic Structure

```bash
.
├── core/                  # Shared logic (parser, clip engine, naming)
├── media/                 # ffprobe analysis and subtitle extraction
├── persistence/           # Project/episode/clip model (JSON save/load)
├── docs/                  # Architecture, data model, changelog
├── cut_clips.py           # CLI: CSV + video → clips + TSV
├── parse_srt_preview.py   # CLI: SRT → preview CSV
├── inspect_media.py       # CLI: analyze tracks, extract subtitles
├── gui_app.py             # GUI: edit timings, preview, cut clips
├── run_gui.sh             # Launch GUI with the project .venv
├── data/                  # Empty in git; optional place for videos
├── requirements.txt
└── README.md
```

## Working folder

Put a series in `data/Serie/SxxExx/` and a movie in `data/Pelicula/`. The repository includes `data/` empty. Git ignores videos, subtitles, clips, projects, and the manifest added there, and keeps `data/.gitkeep` so the folder exists after a clone. Using `data/` is optional.

A series writes `series_manifest.json` in the parent of the episode, for example `data/Serie/`. If the episode folder is named `data`, or its parent is the project root, the file stays inside the episode folder. It is never written in the project root. A movie does not read or write that file, in any folder.

## 0. Inspect Media (recommended first step)

Before extracting subtitles manually, analyze the video file:

```bash
python3 inspect_media.py "episode.mkv" --language en
```

This lists video, audio, and subtitle tracks with absolute and relative indexes,
distinguishes text subtitles from image-based (PGS) tracks, and can extract SRT:

```bash
python3 inspect_media.py "episode.mkv" --extract-subtitle 2 -o S01E01.srt
```

Use the absolute stream index shown in the report (`abs=N`), not the relative audio index.

## Graphical editor (gui_app.py)

An experimental PySide6 GUI lets you review subtitle timings, preview segments
with mpv (A–B loop), merge/delete lines, cut individual clips, and export TSV —
without editing CSV in LibreOffice.

```bash
./run_gui.sh
# equivalent: .venv/bin/python gui_app.py
```

Use the project venv Python. Plain `python3 gui_app.py` fails with `No module named 'PySide6'` if packages were only installed in `.venv`.

On Pop!_OS, double-clicking the script opens the source. Run `./run_gui.sh` in the project directory, or drag `run_gui.sh` onto a terminal, and the interface opens.

Flow: **File → Open video** → review track dialog (ffprobe) →
**Open subtitle (.srt)** or **Extract subtitles from video** (with parser options) →
adjust times → **Cut** → **Export TSV**.

Requires PySide6, python-mpv, libmpv, and `libxcb-cursor0`. Preview works without
cutting; translation at export is optional (DeepL and/or Gemini API keys).

## 1. Extract Subtitles and Create the Preview File

Open a terminal in the directory containing the scripts and video file.

First, select the episode you want to process:

```bash
# Specify the episode
EPISODE="S01E01"

# Find the video file and store its name in a variable
VIDEO1=$(ls Todd.McFarlanes.Spawn.${EPISODE}*.mkv)

# Name of the preview CSV file
CSV1="${EPISODE}_preview.csv"

# Extract the subtitles from the corresponding track
# Prefer inspect_media.py to find the correct stream index:
#   python3 inspect_media.py "$VIDEO1" --extract-subtitle N -o "${EPISODE}.srt"
ffmpeg -i "$VIDEO1" -map 0:2 "${EPISODE}.srt"

# Create a CSV file for manually reviewing and correcting
# subtitle timestamps and text
python3 parse_srt_preview.py "${EPISODE}.srt" -o "$CSV1" --shift -0.4
```

The generated `.csv` file allows you to review the subtitles before creating the final clips.

If a subtitle starts or ends too early or too late, you can manually adjust its timestamps in this file.

## 2. Generate Video + Audio Clips

To enable automatic translation, configure your DeepL API key:

```bash
# DEEPL API
export DEEPL_API_KEY="Replace this with your API key"

# Generar clips (video + audio)
python3 cut_clips.py \
  --video "$VIDEO1" \
  --csv "$CSV1" \
  --series-name Todd_McFarlanes_Spawn_Anki_Video \
  --episode-label S01-Ep01 \
  --media both \
  --translate \
  --limit 5
```

The `--limit 5` option is useful for testing the process with a small number of clips before processing the entire episode.

Once you have verified that the clips are generated correctly, increase the `--limit` value to continue processing the episode.

### Notes

- A valid DeepL API key is required for automatic translation.
- To process more clips, increase the value of `--limit 5` or remove the limit according to the options supported by the program.
- It is recommended to test the process with a small number of clips before processing an entire episode.

☣️☢️ Important 🔥☠️

You must change the names of the files listed in the commands to be executed, depending on your specific situation.

## 3. Continue the Numbering from the Next Episode

After finishing an episode, you can retrieve the ID of the last generated clip:

```bash
# Get the ID of the last generated clip
tail -n1 Todd_McFarlanes_Spawn_Anki_Video_S01-Ep01_anki.tsv | cut -f1

# Get the ID of the last generated clip
LAST_ID=$(tail -n1 Todd_McFarlanes_Spawn_Anki_Video_S01-Ep01_anki.tsv | cut -f1)

# Calculate the next ID
NEXT_START=$((10#$LAST_ID + 1))
echo $NEXT_START
```

> **Note:** If this is the first episode you are processing, `--start-index` is not required.

## 4. Process the Next Episode

For example, to process episode `S01E02`:

```bash
# Specify the episode
EPISODE="S01E02"

# Find the video file
VIDEO2=$(ls Todd.McFarlanes.Spawn.${EPISODE}*.mkv)

# Name of the preview CSV file
CSV2="${EPISODE}_preview.csv"

# Extract the subtitles
ffmpeg -i "$VIDEO2" -map 0:2 "${EPISODE}.srt"

# Create the CSV for manually reviewing and correcting
# subtitle timestamps and text
python3 parse_srt_preview.py "${EPISODE}.srt" -o "$CSV2" --shift -0.4
```

Then generate the clips:

```bash
# DEEPL API para traducir texto
export DEEPL_API_KEY="Replace this with your API key"

# Generar clips (video + audio)
python3 cut_clips.py \
  --video "$VIDEO2" \
  --csv "$CSV2" \
  --series-name Todd_McFarlanes_Spawn_Anki_Video \
  --episode-label S01-Ep02 \
  --start-index $NEXT_START \
  --media both \
  --translate \
  --limit 5
```

The `--start-index` option allows the clip numbering to continue from the previous episode.

## 5. Generate Audio Only

If you only need audio files, use `--media audio`:

```bash
python3 cut_clips.py \
  --video "Todd.McFarlanes.Spawn.S01E01.1080p.HMAX.WEB-DL.DD2.0.H.264-SLiGNOME.mkv" \
  --csv S01E01_preview.csv \
  --series-name Todd_McFarlanes_Spawn_Anki_Video \
  --episode-label S01-Ep01 \
  --media audio
```

## 6. Fixing an Incorrectly Generated Clip

If a clip was not generated correctly:

1. Delete the corresponding clip from the `output_files` directory.
2. Open the `.csv` file.
3. Manually correct the timestamps or subtitle text.
4. Run the generation command again.

There is no need to regenerate clips that are already correct.

## Project Structure After Processing

After processing an episode, the directory structure will look similar to this:

```bash
.
├── cut_clips.py
├── episodio_info.json
├── output_files 👈🏼👀👇🏼
│   ├── Todd_McFarlanes_Spawn_Anki_Video_S01-Ep01_Line_0001.webm
│   ├── Todd_McFarlanes_Spawn_Anki_Video_S01-Ep01_Line_0002.webm
│   ├── Todd_McFarlanes_Spawn_Anki_Video_S01-Ep01_Line_0003.webm
│   ├── Todd_McFarlanes_Spawn_Anki_Video_S01-Ep01_Line_.....webm
│   ├── Todd_McFarlanes_Spawn_Anki_Video_S01-Ep01_Line_.....webm
│   ├── Todd_McFarlanes_Spawn_Anki_Video_S01-Ep01_Line_0048.webm
│   ├── Todd_McFarlanes_Spawn_Anki_Video_S01-Ep01_Line_0049.webm
│   └── Todd_McFarlanes_Spawn_Anki_Video_S01-Ep01_Line_0050.webm
├── parse_srt_preview.py
├── S01E01_preview.csv
├── S01E01.srt
├── Todd_McFarlanes_Spawn_Anki_Video_S01-Ep01_anki.tsv
├── Todd_McFarlanes_Spawn_Anki_Video_translations_cache.json
└── Todd.McFarlanes.Spawn.S01E01.1080p.HMAX.WEB-DL.DD2.0.H.264-SLiGNOME.mkv
```

## Workflow

The overall workflow is:

```text
Video (.mkv)
     │
     ▼
Subtitles (.srt)
     │
     ▼
Preview and manual correction
     │
     ▼
CSV (.csv)
     │
     ├──────────────► DeepL Translation
     │
     ▼
Clip generation
     │
     ├──► Video (.webm)
     └──► Audio
     │
     ▼
TSV for Anki
```

The generated TSV file contains the information required to import the clips and text into Anki.