# cut_clips
A tool to cut video clips, translate subtitles, and generate TSV files ready for Anki import.

`cut_clips` is designed to streamline language learning through audiovisual content. The tool processes video episodes to:

- Extract video and/or audio clips from subtitles.
- Manually adjust timestamps and subtitle text before generating the clips.
- Automatically translate subtitles into the target language using the DeepL API.
- Generate a `.tsv` file compatible with Anki imports.
- Maintain sequential clip numbering across multiple episodes.

This makes it possible to turn an entire video episode into Anki study material with just a few steps.

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

- Python 3
- FFmpeg and ffprobe
- Anki for importing the generated `.tsv` file

Optional:

- **DeepL** — automatic translation (`pip install deepl`); requires API key only when using `--translate`
- **GUI** — PySide6, python-mpv, and system libmpv (see [Graphical editor](#graphical-editor-gui_apppy))

Install Python dependencies:

```bash
pip install -r requirements.txt --break-system-packages
```

On Debian/Ubuntu for GUI preview:

```bash
sudo apt install libmpv2   # or libmpv1 depending on your release
```

## Installation

### 1. Install Python 3

Check whether Python 3 is already installed:

```bash
python3 --version
```

If Python 3 is not installed, install it using your system's package manager.

On Debian/Ubuntu:

```bash
sudo apt update
sudo apt install python3 python3-pip
```

### 2. Install FFmpeg

Check whether FFmpeg is already installed:

```bash
ffmpeg -version
```

On Debian/Ubuntu:

```bash
sudo apt update
sudo apt install ffmpeg
```

### 3. Install the DeepL Python Library

The project uses the official DeepL Python library to communicate with the DeepL API.

Install it with:

```bash
pip install deepl --break-system-packages
```

> **Note:** On Debian-based systems, `--break-system-packages` may be required when installing Python packages globally with `pip`. Using a Python virtual environment is recommended if you want to avoid modifying the system Python environment.

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
├── requirements.txt
└── README.md
```

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
python3 gui_app.py
```

Flow: **File → Open video** → review track dialog (ffprobe) →
**Open subtitle (.srt)** or **Extract subtitles from video** (with parser options) →
adjust times → **Cut** → **Export TSV**.

Requires PySide6, python-mpv, and libmpv. Preview works without cutting; translation
at export is optional (DeepL API key or `DEEPL_API_KEY` env var).

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