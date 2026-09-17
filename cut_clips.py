#!/usr/bin/env python3
"""
cut_clips.py (v3 - vídeo + audio independientes, TSV con 7 campos Anki)

Paso 2 del pipeline Anki-Video: toma el CSV generado por parse_srt_preview.py
y el archivo de vídeo original, corta un clip .webm (vídeo+audio) y/o un
.mp3 (solo audio) por cada oración, usando EXACTAMENTE los mismos tiempos
para ambos, y genera el .tsv final listo para importar en Anki.

Sigue decodificando el episodio en UNA SOLA PASADA CONTINUA (sin seeking),
igual que la v2, para evitar el desfase acumulativo de timestamps poco
confiables en el contenedor.

Campos del TSV generado (en este orden):
    id | video | video_reference | video_audio | english_dialogs |
    spanish_dialogues | notes (vacío)

    video             -> nombre de archivo plano del .webm (sin [sound:])
    video_reference   -> [sound:archivo.webm]
    video_audio       -> [sound:archivo.mp3]

Uso (prueba rápida, solo 5 líneas, generando vídeo Y audio):
    python3 cut_clips.py \
        --video "Todd.McFarlanes.Spawn.S01E01.1080p.HMAX.WEB-DL.DD2.0.H.264-SLiGNOME.mkv" \
        --csv S01E01_preview.csv \
        --series-name Todd_McFarlanes_Spawn_Anki_Video \
        --episode-label S01-Ep01 \
        --media both \
        --limit 5

Solo generar los .mp3 que falten (los .webm ya existen):
    python3 cut_clips.py \
        --video "..." --csv ... --series-name ... --episode-label ... \
        --media audio

Salida:
    output_files/..._Line_0001.webm
    output_files/..._Line_0001.mp3
    Todd_McFarlanes_Spawn_Anki_Video_S01-Ep01_anki.tsv
"""

import argparse
import csv
import json
import subprocess
import sys
import os


# ---------------------------------------------------------------------------
# Traducción (DeepL) con caché local
# ---------------------------------------------------------------------------

def load_translation_cache(cache_path):
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_translation_cache(cache_path, cache):
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def translate_texts(texts, api_key, target_lang, cache_path):
    """Traduce una lista de textos usando DeepL, reutilizando una caché
    local (JSON) para no volver a traducir líneas ya traducidas antes."""
    import deepl

    cache = load_translation_cache(cache_path)
    to_translate = [t for t in set(texts) if t not in cache]

    if to_translate:
        translator = deepl.Translator(api_key)
        print(f"Traduciendo {len(to_translate)} línea(s) nueva(s) con DeepL "
              f"(ya en caché: {len(set(texts)) - len(to_translate)})...")
        results = translator.translate_text(to_translate, target_lang=target_lang)
        for original, result in zip(to_translate, results):
            cache[original] = result.text
        save_translation_cache(cache_path, cache)
    else:
        print("Todas las líneas ya estaban traducidas en la caché, no se llamó a la API.")

    return {t: cache[t] for t in texts}


# ---------------------------------------------------------------------------
# CSV -> ventanas de tiempo
# ---------------------------------------------------------------------------

def parse_timestamp(ts):
    """'HH:MM:SS.mmm' -> segundos (float)."""
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def load_sentences(csv_path):
    sentences = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sentences.append({
                "start": parse_timestamp(row["start"]),
                "end": parse_timestamp(row["end"]),
                "text": row["text"],
            })
    return sentences


def compute_padded_windows(sentences, padding):
    """Aplica padding pero sin invadir el espacio de la línea vecina."""
    n = len(sentences)
    windows = []
    for i, s in enumerate(sentences):
        prev_end = sentences[i - 1]["end"] if i > 0 else None
        next_start = sentences[i + 1]["start"] if i < n - 1 else None

        padded_start = s["start"] - padding
        if padded_start < 0:
            padded_start = 0.0
        if prev_end is not None:
            padded_start = max(padded_start, prev_end)

        padded_end = s["end"] + padding
        if next_start is not None:
            padded_end = min(padded_end, next_start)

        windows.append((padded_start, padded_end))
    return windows


# ---------------------------------------------------------------------------
# Construcción del comando ffmpeg de pasada única
# ---------------------------------------------------------------------------

def build_single_pass_command(video_path, jobs, width, height, crf,
                               webm_audio_bitrate, mp3_bitrate, max_time):
    """jobs: lista de dicts con:
        index, start, end, need_video, need_audio, video_path, audio_path
    Construye UN comando ffmpeg que decodifica el vídeo una sola vez y
    produce todos los .webm y .mp3 necesarios de esa misma pasada, usando
    split/asplit + trim/atrim. Vídeo y audio de una misma línea usan
    exactamente el mismo start/end.
    """
    video_jobs = [j for j in jobs if j["need_video"]]
    audio_jobs = [j for j in jobs if j["need_audio"]]

    total_audio_branches = len(video_jobs) + len(audio_jobs)
    filter_parts = []
    map_args = []

    audio_labels = [f"a{n}" for n in range(total_audio_branches)]
    if audio_labels:
        filter_parts.append(
            "[0:a:0]asplit=" + str(len(audio_labels)) +
            "".join(f"[{lbl}]" for lbl in audio_labels)
        )
    label_pos = 0  # siguiente label de audio libre para asignar

    if video_jobs:
        vlabels = [f"v{j['index']}" for j in video_jobs]
        filter_parts.append(
            "[0:v:0]split=" + str(len(video_jobs)) +
            "".join(f"[{lbl}]" for lbl in vlabels)
        )

        for j, vlbl in zip(video_jobs, vlabels):
            duration = j["end"] - j["start"]
            filter_parts.append(
                f"[{vlbl}]trim=start={j['start']:.3f}:duration={duration:.3f},"
                f"setpts=PTS-STARTPTS,scale={width}:{height}[out_{vlbl}]"
            )
            alabel = audio_labels[label_pos]
            label_pos += 1
            filter_parts.append(
                f"[{alabel}]atrim=start={j['start']:.3f}:duration={duration:.3f},"
                f"asetpts=PTS-STARTPTS[out_{alabel}]"
            )
            map_args += [
                "-map", f"[out_{vlbl}]",
                "-map", f"[out_{alabel}]",
                "-c:v", "libvpx-vp9",
                "-crf", str(crf),
                "-b:v", "0",
                "-deadline", "good",
                "-cpu-used", "3",
                "-c:a", "libopus",
                "-b:a", webm_audio_bitrate,
                j["video_path"],
            ]

    for j in audio_jobs:
        duration = j["end"] - j["start"]
        alabel = audio_labels[label_pos]
        label_pos += 1
        filter_parts.append(
            f"[{alabel}]atrim=start={j['start']:.3f}:duration={duration:.3f},"
            f"asetpts=PTS-STARTPTS[out_{alabel}]"
        )
        map_args += [
            "-map", f"[out_{alabel}]",
            "-c:a", "libmp3lame",
            "-b:a", mp3_bitrate,
            j["audio_path"],
        ]

    filter_complex = ";".join(filter_parts)

    cmd = ["ffmpeg", "-y", "-t", f"{max_time:.3f}", "-i", video_path,
           "-filter_complex", filter_complex] + map_args + ["-loglevel", "error"]
    return cmd


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

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
                         help="Default: {series-name}_{episode-label}_anki.tsv")
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
    parser.add_argument("--limit", type=int, default=None,
                         help="Procesar solo las primeras N líneas (prueba rápida)")
    parser.add_argument("--start-index", type=int, default=1,
                         help="Número desde el que empezar a contar el id/Line_XXXX "
                              "(default: 1). Útil para continuar la numeración de un "
                              "episodio anterior, ej. --start-index 185 si el episodio "
                              "previo terminó en la línea 184, y así mantener ids únicos "
                              "en toda la colección de Anki.")
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

    if args.tsv_out is None:
        args.tsv_out = f"{args.series_name}_{args.episode_label}_anki.tsv"

    os.makedirs(args.output_dir, exist_ok=True)

    sentences = load_sentences(args.csv)
    if args.limit:
        sentences = sentences[:args.limit]

    windows = compute_padded_windows(sentences, args.padding)

    want_video = args.media in ("video", "both")
    want_audio = args.media in ("audio", "both")

    jobs = []
    tsv_rows = []  # (id, text, video_filename, audio_filename)
    video_skipped = 0
    audio_skipped = 0
    invalid_lines = []

    MIN_DURATION = 0.05  # segundos; por debajo de esto se considera inválido

    for i, (sentence, (start, end)) in enumerate(zip(sentences, windows), start=args.start_index):
        video_filename = f"{args.series_name}_{args.episode_label}_Line_{i:04d}.webm"
        audio_filename = f"{args.series_name}_{args.episode_label}_Line_{i:04d}.mp3"
        video_path = os.path.join(args.output_dir, video_filename)
        audio_path = os.path.join(args.output_dir, audio_filename)

        tsv_rows.append((i, sentence["text"], video_filename, audio_filename))

        if end - start < MIN_DURATION:
            invalid_lines.append((i, start, end, sentence["text"]))
            continue  # no se agrega a 'jobs': se excluye del lote, no tumba el resto

        need_video = want_video and (args.overwrite or not os.path.exists(video_path))
        need_audio = want_audio and (args.overwrite or not os.path.exists(audio_path))

        if want_video and not need_video:
            video_skipped += 1
        if want_audio and not need_audio:
            audio_skipped += 1

        if need_video or need_audio:
            jobs.append({
                "index": i,
                "start": start,
                "end": end,
                "need_video": need_video,
                "need_audio": need_audio,
                "video_path": video_path,
                "audio_path": audio_path,
            })

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

    video_generated = video_errors = 0
    audio_generated = audio_errors = 0

    if jobs:
        max_time = max(j["end"] for j in jobs) + 1.0
        print(f"\nDecodificando el episodio en una sola pasada hasta el segundo {max_time:.1f}...")
        cmd = build_single_pass_command(
            args.video, jobs, args.width, args.height, args.crf,
            args.audio_bitrate, args.mp3_bitrate, max_time,
        )
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print("\n[ERROR] ffmpeg falló en la pasada completa:")
            print(result.stderr.strip()[-2000:])
        else:
            for j in jobs:
                if j["need_video"]:
                    if os.path.exists(j["video_path"]) and os.path.getsize(j["video_path"]) > 0:
                        video_generated += 1
                    else:
                        video_errors += 1
                        print(f"  [ERROR] No se generó: {j['video_path']}")
                if j["need_audio"]:
                    if os.path.exists(j["audio_path"]) and os.path.getsize(j["audio_path"]) > 0:
                        audio_generated += 1
                    else:
                        audio_errors += 1
                        print(f"  [ERROR] No se generó: {j['audio_path']}")

    translations = {}
    if args.translate:
        api_key = args.deepl_key or os.environ.get("DEEPL_API_KEY")
        if not api_key:
            print("\n[ERROR] --translate requiere una API key de DeepL.")
            print("Pásala con --deepl-key o expórtala como variable de entorno:")
            print('  export DEEPL_API_KEY="tu-api-key-aqui"')
            sys.exit(1)

        cache_path = args.translation_cache or f"{args.series_name}_translations_cache.json"
        all_texts = [text for _, text, _, _ in tsv_rows]
        translations = translate_texts(all_texts, api_key, args.target_lang, cache_path)

    # Campos del TSV, en el orden de la nota Anki:
    # id | video | video_reference | video_audio | english_dialogs | spanish_dialogues | notes
    with open(args.tsv_out, "w", encoding="utf-8", newline="") as f:
        for i, text, video_filename, audio_filename in tsv_rows:
            translation = translations.get(text, "")
            video_field = video_filename
            video_reference_field = f"[sound:{video_filename}]"
            video_audio_field = f"[sound:{audio_filename}]"
            notes_field = ""
            f.write(
                f"{i:04d}\t{video_field}\t{video_reference_field}\t{video_audio_field}\t"
                f"{text}\t{translation}\t{notes_field}\n"
            )

    def total_size(paths):
        return sum(os.path.getsize(p) for p in paths if os.path.exists(p))

    video_size_mb = total_size(
        os.path.join(args.output_dir, vf) for _, _, vf, _ in tsv_rows
    ) / (1024 * 1024)
    audio_size_mb = total_size(
        os.path.join(args.output_dir, af) for _, _, _, af in tsv_rows
    ) / (1024 * 1024)

    print()
    if want_video:
        print(f"Vídeo generado: {video_generated}  |  errores: {video_errors}  |  tamaño total: {video_size_mb:.1f} MB")
    if want_audio:
        print(f"Audio generado: {audio_generated}  |  errores: {audio_errors}  |  tamaño total: {audio_size_mb:.1f} MB")
    print(f"\nTSV generado: {args.tsv_out}")
    print(f"Archivos en: {args.output_dir}/")


if __name__ == "__main__":
    main()