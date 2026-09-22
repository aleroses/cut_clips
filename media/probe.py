"""Análisis de archivos multimedia con ffprobe y extracción de subtítulos."""

import json
import os
import subprocess
import sys

TEXT_SUBTITLE_CODECS = {"subrip", "ass", "ssa", "mov_text", "webvtt"}
IMAGE_SUBTITLE_CODECS = {"hdmv_pgs_subtitle", "dvd_subtitle", "xsub"}

LANGUAGE_ALIASES = {
    "en": {"eng"}, "es": {"spa"}, "fr": {"fre", "fra"}, "de": {"ger", "deu"},
    "it": {"ita"}, "pt": {"por"}, "ja": {"jpn"}, "zh": {"chi", "zho"},
    "ko": {"kor"}, "ru": {"rus"}, "nl": {"dut", "nld"}, "sv": {"swe"},
    "pl": {"pol"}, "ar": {"ara"},
}


def language_matches(stream_lang, requested_lang):
    """Compara el idioma de una pista (ISO 639-2/3) con el código pedido (2 o 3 letras)."""
    stream_lang = (stream_lang or "").lower()
    requested_lang = (requested_lang or "").lower()
    if stream_lang == requested_lang:
        return True
    return stream_lang in LANGUAGE_ALIASES.get(requested_lang, set())


def probe(video_path, exit_on_error=True):
    """Ejecuta ffprobe y devuelve el dict JSON de format/streams."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", video_path],
            capture_output=True, text=True, timeout=60,
        )
    except FileNotFoundError:
        if exit_on_error:
            print("[ERROR] ffprobe no está instalado.", file=sys.stderr)
            sys.exit(1)
        raise
    if result.returncode != 0:
        if exit_on_error:
            print(f"[ERROR] ffprobe falló:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)
        raise RuntimeError(result.stderr.strip())
    return json.loads(result.stdout)


def get_episode_title(data):
    return data.get("format", {}).get("tags", {}).get("title", "")


def get_format_info(data):
    """Resumen del contenedor: duración, bitrate, título."""
    fmt = data.get("format", {})
    duration = float(fmt.get("duration", 0) or 0)
    bitrate = fmt.get("bit_rate")
    return {
        "title": fmt.get("tags", {}).get("title", ""),
        "duration_sec": duration,
        "duration_min": duration / 60.0 if duration else 0.0,
        "bitrate": int(bitrate) if bitrate else None,
        "format_name": fmt.get("format_name", "?"),
    }


def subtitle_kind_label(subtitle_entry):
    """Etiqueta legible del tipo de subtítulo."""
    if subtitle_entry.get("is_text"):
        return "Texto (extraíble a .srt)"
    if subtitle_entry.get("is_image"):
        return "Imagen (PGS/VobSub — no editable como texto)"
    return f"Desconocido ({subtitle_entry.get('codec_name', '?')})"


def suggest_tracks(video, audio, subtitles, language="en"):
    """Sugiere índices de pista por idioma. Devuelve dict con claves seleccionadas."""
    video_track = 0
    if video:
        lang_video = video  # vídeo raramente tiene idioma distinto por pista
        video_track = lang_video[0].get("relative_index", 0)

    audio_track = 0
    lang_audio = [a for a in audio if language_matches(a["language"], language)]
    if lang_audio:
        audio_track = lang_audio[0]["relative_index"]
    elif audio:
        audio_track = audio[0]["relative_index"]

    subtitle_index = None
    text_subs = [s for s in subtitles if s.get("is_text")]
    lang_text = [s for s in text_subs if language_matches(s["language"], language)]
    if len(lang_text) == 1:
        subtitle_index = lang_text[0]["index"]
    elif len(text_subs) == 1:
        subtitle_index = text_subs[0]["index"]
    elif lang_text:
        subtitle_index = lang_text[0]["index"]

    return {
        "video_track": video_track,
        "audio_track": audio_track,
        "subtitle_track_index": subtitle_index,
    }


def summarize_media(data):
    """Resumen estructurado para GUI o persistencia."""
    video, audio, subtitles = classify_streams(data)
    return {
        "format": get_format_info(data),
        "video": video,
        "audio": audio,
        "subtitles": subtitles,
    }


def find_subtitle_stream(subtitles, stream_index):
    """Busca una pista de subtítulo por índice absoluto ffprobe."""
    for entry in subtitles:
        if entry["index"] == stream_index:
            return entry
    return None


def subtitle_extract_path(video_path, stream_index):
    """Ruta sugerida para guardar un SRT extraído junto al vídeo."""
    base, _ = os.path.splitext(video_path)
    return f"{base}.track{stream_index}.srt"


def find_sidecar_subtitle(video_path: str) -> str | None:
    """Busca un .srt junto al vídeo (mismo basename o nombre.mkv.srt)."""
    video_path = os.path.abspath(video_path)
    base, _ = os.path.splitext(video_path)
    for candidate in (f"{base}.srt", f"{video_path}.srt"):
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


def classify_streams(data):
    """Clasifica streams en listas de vídeo, audio y subtítulos."""
    video, audio, subtitles = [], [], []
    audio_rel = 0
    video_rel = 0
    subtitle_rel = 0
    for s in data.get("streams", []):
        kind = s.get("codec_type")
        entry = {
            "index": s["index"],
            "codec_name": s.get("codec_name", "?"),
            "language": s.get("tags", {}).get("language", "?"),
            "title": s.get("tags", {}).get("title", ""),
        }
        if kind == "video":
            entry["resolution"] = f"{s.get('width', '?')}x{s.get('height', '?')}"
            entry["fps"] = _format_fps(s)
            entry["bitrate"] = s.get("bit_rate")
            entry["relative_index"] = video_rel
            video_rel += 1
            video.append(entry)
        elif kind == "audio":
            entry["channels"] = s.get("channels", "?")
            entry["sample_rate"] = s.get("sample_rate", "?")
            entry["relative_index"] = audio_rel
            audio_rel += 1
            audio.append(entry)
        elif kind == "subtitle":
            codec = entry["codec_name"]
            entry["is_text"] = codec in TEXT_SUBTITLE_CODECS
            entry["is_image"] = codec in IMAGE_SUBTITLE_CODECS
            entry["relative_index"] = subtitle_rel
            subtitle_rel += 1
            subtitles.append(entry)
    return video, audio, subtitles


def _format_fps(stream):
    rate = stream.get("r_frame_rate") or stream.get("avg_frame_rate")
    if not rate or rate == "0/0":
        return "?"
    if "/" in rate:
        num, den = rate.split("/", 1)
        try:
            den_f = float(den)
            if den_f == 0:
                return rate
            return f"{float(num) / den_f:.3f}"
        except ValueError:
            return rate
    return rate


def extract_subtitle(video_path, stream_index, output_path, exit_on_error=True):
    """Extrae una pista de subtítulos a archivo (p. ej. .srt)."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-map", f"0:{stream_index}", output_path],
            capture_output=True, text=True, timeout=300,
        )
    except FileNotFoundError:
        if exit_on_error:
            print("[ERROR] ffmpeg no está instalado.", file=sys.stderr)
            sys.exit(1)
        raise
    if result.returncode != 0:
        if exit_on_error:
            print(
                f"[ERROR] No se pudo extraer la pista {stream_index}:\n{result.stderr}",
                file=sys.stderr,
            )
            sys.exit(1)
        raise RuntimeError(result.stderr.strip())
    return output_path
