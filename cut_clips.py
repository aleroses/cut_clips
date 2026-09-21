#!/usr/bin/env python3
"""
cut_clips.py (v4 - envoltorio delgado sobre core/clip_engine.py)

Paso 2 del pipeline Anki-Video: toma el CSV generado por parse_srt_preview.py
y el archivo de vídeo original, corta un clip .webm (vídeo+audio) y/o un
.mp3 (solo audio) por cada oración, usando EXACTAMENTE los mismos tiempos
para ambos, y genera el .tsv final listo para importar en Anki.

Toda la lógica real vive ahora en core/clip_engine.py, para poder
reutilizarla desde la futura GUI. Este archivo solo maneja argumentos de
línea de comandos y el reporte en pantalla — el comportamiento es
idéntico al de la versión anterior (v3).

Uso (prueba rápida, solo 5 líneas, generando vídeo Y audio):
    python3 cut_clips.py \
        --video "Todd.McFarlanes.Spawn.S01E01.1080p.HMAX.WEB-DL.DD2.0.H.264-SLiGNOME.mkv" \
        --csv S01E01_preview.csv \
        --series-name Todd_McFarlanes_Spawn_Anki_Video \
        --episode-label S01-Ep01 \
        --media both \
        --limit 5
"""

import argparse
import os
import sys

from core.clip_engine import (
    load_sentences_from_csv,
    compute_padded_windows,
    validate_and_build_jobs,
    run_batch,
    write_anki_tsv,
    compute_media_sizes,
    translate_texts,
    detect_video_title,
    extract_episode_title,
    sanitize_filename_component,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, help="Ruta al .mkv original")
    parser.add_argument("--csv", required=True, help="CSV generado por parse_srt_preview.py")
    parser.add_argument("--series-name", required=True,
                         help="Ej: Todd_McFarlanes_Spawn_Anki_Video")
    parser.add_argument("--episode-label", required=True,
                         help="Ej: S01-Ep01")
    parser.add_argument("--output-dir", default="output_files")
    parser.add_argument("--tsv-out", default=None,
                         help="Default: {series-name}_{episode-label}_{episode-title}_anki.tsv")
    parser.add_argument("--episode-title", default=None,
                         help="Título del episodio para el nombre del TSV (ej. 'Burning "
                              "Visions'). Si no se pasa, se intenta detectar automáticamente "
                              "desde el metadato 'title' del .mkv.")
    parser.add_argument("--padding", type=float, default=0.0,
                         help="Segundos de margen antes/después (default: 0.0)")
    parser.add_argument("--media", choices=["video", "audio", "both"], default="both",
                         help="Qué archivos generar: solo vídeo (.webm), solo audio "
                              "(.mp3), o ambos (default: both)")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--crf", type=int, default=32)
    parser.add_argument("--audio-bitrate", default="96k",
                         help="Bitrate del audio EMBEBIDO en el .webm (default: 96k)")
    parser.add_argument("--mp3-bitrate", default="128k",
                         help="Bitrate del .mp3 independiente (default: 128k)")
    parser.add_argument("--audio-track", type=int, default=0,
                         help="Índice RELATIVO de la pista de audio a usar (0 = primera, "
                              "1 = segunda, etc.). Útil si el .mkv trae varios idiomas de "
                              "audio. Usa inspect_media.py para ver las pistas disponibles. "
                              "(default: 0)")
    parser.add_argument("--video-track", type=int, default=0,
                         help="Índice RELATIVO de la pista de vídeo a usar (default: 0)")
    parser.add_argument("--limit", type=int, default=None,
                         help="Procesar solo las primeras N líneas (prueba rápida)")
    parser.add_argument("--start-index", type=int, default=1,
                         help="Número desde el que empezar a contar el id/Line_XXXX "
                              "(default: 1). Útil para continuar la numeración de un "
                              "episodio anterior, ej. --start-index 185.")
    parser.add_argument("--overwrite", action="store_true",
                         help="Regenerar archivos que ya existen")
    parser.add_argument("--translate", action="store_true",
                         help="Traducir cada línea con DeepL y ponerla en el campo spanish_dialogues")
    parser.add_argument("--deepl-key", default=None,
                         help="API key de DeepL. Si no se pasa, se lee de la variable de "
                              "entorno DEEPL_API_KEY")
    parser.add_argument("--target-lang", default="ES",
                         help="Idioma destino de la traducción (default: ES)")
    parser.add_argument("--translation-cache", default=None,
                         help="Ruta del archivo de caché de traducciones "
                              "(default: {series-name}_translations_cache.json)")
    args = parser.parse_args()

    episode_title = args.episode_title
    title_source = "manual (--episode-title)"
    if not episode_title:
        raw_title = detect_video_title(args.video)
        episode_title = extract_episode_title(raw_title)
        title_source = "detectado automáticamente del .mkv" if episode_title else None

    if episode_title:
        print(f"Título del episodio: \"{episode_title}\" ({title_source})")
        title_slug = sanitize_filename_component(episode_title)
        default_tsv_name = f"{args.series_name}_{args.episode_label}_{title_slug}_anki.tsv"
    else:
        print("Título del episodio: no detectado ni proporcionado (--episode-title), "
              "se omite del nombre del TSV.")
        default_tsv_name = f"{args.series_name}_{args.episode_label}_anki.tsv"

    if args.tsv_out is None:
        args.tsv_out = default_tsv_name

    os.makedirs(args.output_dir, exist_ok=True)

    sentences = load_sentences_from_csv(args.csv)
    if args.limit:
        sentences = sentences[:args.limit]

    windows = compute_padded_windows(sentences, args.padding)

    want_video = args.media in ("video", "both")
    want_audio = args.media in ("audio", "both")

    jobs, tsv_rows, video_skipped, audio_skipped, invalid_lines = validate_and_build_jobs(
        sentences, windows, args.series_name, args.episode_label, args.output_dir,
        want_video, want_audio, args.overwrite, start_index=args.start_index,
        episode_title=episode_title or "",
    )

    if invalid_lines:
        print(f"\n[AVISO] {len(invalid_lines)} línea(s) con tiempo inválido (end <= start), excluidas de este lote:")
        for i, start, end, text in invalid_lines:
            print(f"  Línea {i:04d}: start={start:.3f}  end={end:.3f}  ({end - start:+.3f}s)  \"{text[:60]}\"")
        print("  Revisa y corrige estas líneas en el CSV (columnas 'start'/'end').\n")

    print(f"Líneas totales:            {len(sentences)}")
    if want_video:
        print(f"Vídeo ya existía (omitido): {video_skipped}")
    if want_audio:
        print(f"Audio ya existía (omitido): {audio_skipped}")
    print(f"Líneas con trabajo pendiente: {len(jobs)}")

    video_generated = video_errors = audio_generated = audio_errors = 0

    if jobs:
        max_time = max(j["end"] for j in jobs) + 1.0
        print(f"\nDecodificando el episodio en una sola pasada hasta el segundo {max_time:.1f}...")
        video_generated, video_errors, audio_generated, audio_errors, error_message = run_batch(
            args.video, jobs, args.width, args.height, args.crf,
            args.audio_bitrate, args.mp3_bitrate,
            audio_track=args.audio_track, video_track=args.video_track,
        )
        if error_message:
            print("\n[ERROR] ffmpeg falló en la pasada completa:")
            print(error_message)

    translations = {}
    if args.translate:
        api_key = args.deepl_key or os.environ.get("DEEPL_API_KEY")
        if not api_key:
            print("\n[ERROR] --translate requiere una API key de DeepL.")
            print("Pásala con --deepl-key o expórtala como variable de entorno:")
            print('  export DEEPL_API_KEY="tu-api-key-aqui"')
            sys.exit(1)

        cache_path = args.translation_cache or f"{args.series_name}_translations_cache.json"
        all_texts = [text for _, text, _, _, _, _ in tsv_rows]
        translations = translate_texts(all_texts, api_key, args.target_lang, cache_path)

    write_anki_tsv(args.tsv_out, tsv_rows, translations)

    video_size_mb, audio_size_mb = compute_media_sizes(tsv_rows, args.output_dir)

    print()
    if want_video:
        print(f"Vídeo generado: {video_generated}  |  errores: {video_errors}  |  tamaño total: {video_size_mb:.1f} MB")
    if want_audio:
        print(f"Audio generado: {audio_generated}  |  errores: {audio_errors}  |  tamaño total: {audio_size_mb:.1f} MB")
    print(f"\nTSV generado: {args.tsv_out}")
    print(f"Archivos en: {args.output_dir}/")


if __name__ == "__main__":
    main()