#!/usr/bin/env python3
"""
inspect_media.py

Automatiza el análisis que antes se hacía a mano con ffprobe antes de
empezar a trabajar con un episodio nuevo:

    ffprobe -v error -show_entries stream=... -of default=... "video.mkv"
    ffprobe -v error -print_format json -show_format -show_streams "video.mkv"

Este script:
    1. Lista todas las pistas de vídeo/audio/subtítulos con su índice,
       códec e idioma.
    2. Distingue subtítulos de TEXTO (subrip, ass, mov_text, webvtt) de
       subtítulos de IMAGEN (hdmv_pgs_subtitle, dvd_subtitle) que
       necesitarían OCR — algo que antes había que descubrir a mano
       leyendo la salida de ffprobe.
    3. Filtra por idioma (--language) para sugerir qué pista de audio y
       de subtítulos usar cuando hay varias.
    4. Extrae el título del episodio (metadata del contenedor), útil
       para la columna 'episode_title' del TSV.
    5. Opcionalmente extrae la pista de subtítulos elegida directo a .srt
       (--extract-subtitle N -o archivo.srt), reemplazando el
       "ffmpeg -map 0:N archivo.srt" manual.

Uso:
    # Solo reporte, sin extraer nada
    python3 inspect_media.py "episodio.mkv"

    # Filtrar por idioma
    python3 inspect_media.py "episodio.mkv" --language fr

    # Extraer directamente la pista de subtítulos con índice 2
    python3 inspect_media.py "episodio.mkv" --extract-subtitle 2 -o episodio.srt
"""

import argparse
import json
import subprocess
import sys

TEXT_SUBTITLE_CODECS = {"subrip", "ass", "ssa", "mov_text", "webvtt"}
IMAGE_SUBTITLE_CODECS = {"hdmv_pgs_subtitle", "dvd_subtitle", "xsub"}

# ffprobe reporta idiomas en ISO 639-2 (3 letras), pero es más natural que
# el usuario escriba el código de 2 letras (ISO 639-1). Mapeamos los más
# comunes; si el usuario ya escribe el de 3 letras, también funciona.
LANGUAGE_ALIASES = {
    "en": {"eng"}, "es": {"spa"}, "fr": {"fre", "fra"}, "de": {"ger", "deu"},
    "it": {"ita"}, "pt": {"por"}, "ja": {"jpn"}, "zh": {"chi", "zho"},
    "ko": {"kor"}, "ru": {"rus"}, "nl": {"dut", "nld"}, "sv": {"swe"},
    "pl": {"pol"}, "ar": {"ara"},
}


def language_matches(stream_lang, requested_lang):
    """Compara el idioma de una pista (código de 3 letras de ffprobe) con
    lo que pidió el usuario, aceptando tanto 2 como 3 letras de su parte."""
    stream_lang = (stream_lang or "").lower()
    requested_lang = (requested_lang or "").lower()
    if stream_lang == requested_lang:
        return True
    return stream_lang in LANGUAGE_ALIASES.get(requested_lang, set())


def probe(video_path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", video_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"[ERROR] ffprobe falló:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def get_episode_title(data):
    return data.get("format", {}).get("tags", {}).get("title", "")


def classify_streams(data):
    video, audio, subtitles = [], [], []
    audio_rel = 0
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
            video.append(entry)
        elif kind == "audio":
            entry["channels"] = s.get("channels", "?")
            entry["relative_index"] = audio_rel  # el N que usa ffmpeg en 0:a:N
            audio_rel += 1
            audio.append(entry)
        elif kind == "subtitle":
            codec = entry["codec_name"]
            entry["is_text"] = codec in TEXT_SUBTITLE_CODECS
            entry["is_image"] = codec in IMAGE_SUBTITLE_CODECS
            entry["relative_index"] = subtitle_rel  # el N que usa ffmpeg en 0:s:N
            subtitle_rel += 1
            subtitles.append(entry)
    return video, audio, subtitles


def print_report(video_path, data, language):
    title = get_episode_title(data)
    duration = float(data.get("format", {}).get("duration", 0))
    video, audio, subtitles = classify_streams(data)

    print(f"Archivo: {video_path}")
    if title:
        print(f"Título (metadata): {title}")
    print(f"Duración: {duration/60:.1f} min\n")

    print("VÍDEO:")
    for v in video:
        print(f"  [{v['index']}] {v['codec_name']}  {v['resolution']}")

    print("\nAUDIO:")
    for a in audio:
        marker = "  <-- coincide con --language" if language_matches(a["language"], language) else ""
        print(f"  [abs={a['index']}, audio_track={a['relative_index']}] {a['codec_name']}  "
              f"idioma={a['language']}  canales={a['channels']}  título=\"{a['title']}\"{marker}")

    print("\nSUBTÍTULOS:")
    if not subtitles:
        print("  (ninguna pista de subtítulos encontrada en el contenedor —"
              " si tienes un .srt/.vtt suelto, pásalo directo a parse_srt_preview.py)")
    for s in subtitles:
        if s["is_text"]:
            kind = "TEXTO (se puede extraer directo a .srt)"
        elif s["is_image"]:
            kind = "IMAGEN (necesita OCR, ej. pgsrip — no soportado aún en este pipeline)"
        else:
            kind = f"desconocido ({s['codec_name']})"
        marker = "  <-- coincide con --language" if language_matches(s["language"], language) else ""
        print(f"  [abs={s['index']}] {s['codec_name']}  idioma={s['language']}  "
              f"título=\"{s['title']}\"  -> {kind}{marker}")

    if len(audio) > 1:
        print(f"\n[INFO] Hay {len(audio)} pistas de audio. Usa --audio-track N en "
              f"cut_clips.py con el número 'audio_track' de arriba (no el 'abs') "
              f"para elegir cuál usar.")

    # Sugerencia automática
    text_matches = [s for s in subtitles if s["is_text"] and language_matches(s["language"], language)]
    if len(text_matches) == 1:
        print(f"\nSugerencia: usa el índice {text_matches[0]['index']} para extraer "
              f"el subtítulo en '{language}':")
        print(f"  python3 inspect_media.py \"{video_path}\" "
              f"--extract-subtitle {text_matches[0]['index']} -o episodio.srt")
    elif len(text_matches) > 1:
        print(f"\n[AVISO] Hay {len(text_matches)} pistas de texto en '{language}' — "
              f"revisa el título de cada una para elegir la correcta.")
    elif not any(s["is_text"] for s in subtitles) and any(s["is_image"] for s in subtitles):
        print(f"\n[AVISO] Solo hay subtítulos de IMAGEN — este pipeline no soporta "
              f"OCR todavía, necesitarías un .srt/.vtt de otra fuente.")


def extract_subtitle(video_path, stream_index, output_path):
    cmd = ["ffmpeg", "-y", "-i", video_path, "-map", f"0:{stream_index}", output_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERROR] No se pudo extraer la pista {stream_index}:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    print(f"Subtítulo extraído: {output_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video", help="Ruta al archivo de vídeo (.mkv, .mp4, etc.)")
    parser.add_argument("--language", default="en",
                         help="Código de idioma a buscar entre las pistas (default: en)")
    parser.add_argument("--extract-subtitle", type=int, default=None,
                         help="Índice de la pista de subtítulos a extraer directamente")
    parser.add_argument("-o", "--output", default=None,
                         help="Ruta de salida para --extract-subtitle (ej: episodio.srt)")
    parser.add_argument("--json-out", default=None,
                         help="Guardar la salida completa de ffprobe en este archivo .json")
    args = parser.parse_args()

    data = probe(args.video)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Info completa guardada en: {args.json_out}\n")

    if args.extract_subtitle is not None:
        if not args.output:
            print("[ERROR] --extract-subtitle requiere -o/--output", file=sys.stderr)
            sys.exit(1)
        extract_subtitle(args.video, args.extract_subtitle, args.output)
    else:
        print_report(args.video, data, args.language)


if __name__ == "__main__":
    main()