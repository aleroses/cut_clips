#!/usr/bin/env python3
"""
parse_srt_preview.py

Paso 1 del pipeline Anki-Video: parsea un .srt SDH, agrupa fragmentos de
subtítulo en oraciones completas y filtra bloques que son solo efectos de
sonido / etiquetas de hablante sin diálogo. NO corta vídeo todavía — solo
genera una tabla (CSV) para que revises que la agrupación es correcta.

Uso:
    python3 parse_srt_preview.py S01E01.srt -o S01E01_preview.csv
    python3 parse_srt_preview.py S01E01.srt -o S01E01_preview.csv --min-duration 1.0 --min-words 2

Columnas del CSV de salida:
    line_number, start, end, duration_sec, text
"""

import argparse
import csv
import re
import sys

TIME_RE = re.compile(
    r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})'
)
SENTENCE_END_RE = re.compile(r'["\']?[.!?]["\']?\s*$')


def timestamp_to_seconds(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def seconds_to_timestamp(total_seconds):
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"


def parse_srt_blocks(path, offset=0.0, scale=1.0):
    """Devuelve una lista de dicts: {start, end, raw_text} por bloque SRT.

    offset: segundos a sumar a cada tiempo (positivo = atrasar el subtítulo,
            negativo = adelantarlo). Corrige un desfase CONSTANTE.
    scale:  factor multiplicativo aplicado antes del offset. Corrige un
            desfase que CRECE con el tiempo (drift por diferencia de
            framerate entre releases, ej. 23.976 vs 25 fps).
            Fórmula: tiempo_corregido = tiempo_original * scale + offset
    """
    with open(path, encoding="utf-8-sig") as f:
        content = f.read()

    raw_blocks = re.split(r'\n\s*\n', content.strip())
    blocks = []

    for raw_block in raw_blocks:
        lines = [l for l in raw_block.strip("\n").split("\n")]
        ts_idx = None
        for i, line in enumerate(lines):
            if "-->" in line:
                ts_idx = i
                break
        if ts_idx is None:
            continue

        m = TIME_RE.search(lines[ts_idx])
        if not m:
            continue

        h1, m1, s1, ms1, h2, m2, s2, ms2 = m.groups()
        start = timestamp_to_seconds(h1, m1, s1, ms1) * scale + offset
        end = timestamp_to_seconds(h2, m2, s2, ms2) * scale + offset

        text_lines = lines[ts_idx + 1:]
        raw_text = " ".join(l.strip() for l in text_lines if l.strip())

        blocks.append({"start": start, "end": end, "raw_text": raw_text})

    return blocks


def clean_text(raw_text):
    """Quita etiquetas (efectos de sonido / hablante) entre () y []."""
    cleaned = re.sub(r"\([^)]*\)", "", raw_text)
    cleaned = re.sub(r"\[[^\]]*\]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # El SDH suele dejar un espacio antes de la puntuación (ej. "again ?").
    # Lo quitamos para que quede "again?" como se escribe normalmente.
    cleaned = re.sub(r"\s+([?.!,;:])", r"\1", cleaned)
    return cleaned


def normalize_case(text):
    """ALL CAPS -> sentence case. Limitación conocida: nombres propios
    quedarán en minúscula salvo que empiecen oración; se puede mejorar
    luego con una lista de excepciones (nombres de personajes, etc.)."""
    text = text.lower()

    # "i" / "i'm" / "i've" / "i'll" / "i'd" -> "I" / "I'm" / ...
    text = re.sub(r"\bi\b", "I", text)
    text = re.sub(r"\bi'(m|ve|ll|d)\b", lambda m: "I'" + m.group(1), text)

    # Mayúscula al inicio del texto y después de . ! ?
    def cap(match):
        return match.group(1) + match.group(2).upper()

    text = re.sub(r"(^|[.!?]\s+)([a-z])", cap, text)
    return text


def apply_boundary_trim(start, end, trim_start, trim_end, min_duration=0.3):
    """Recorta 'trim_start' segundos al inicio y 'trim_end' al final de una
    oración, para compensar el margen de lectura que traen los subtítulos
    SDH (el texto suele aparecer un poco antes de hablarse y quedarse un
    poco después de terminar). Nunca recorta más del 40% de la duración por
    lado, ni deja una línea más corta que 'min_duration'."""
    duration = end - start
    safe_trim_start = min(trim_start, duration * 0.4)
    safe_trim_end = min(trim_end, duration * 0.4)

    new_start = start + safe_trim_start
    new_end = end - safe_trim_end

    if new_end - new_start < min_duration:
        return start, end  # el recorte dejaría la línea demasiado corta

    return new_start, new_end


def group_into_sentences(blocks, trim_start=0.0, trim_end=0.0):
    """Agrupa bloques consecutivos hasta encontrar puntuación de cierre.
    Descarta bloques que quedan vacíos tras limpiar (solo efectos de sonido).
    Aplica trim_start/trim_end a los límites de cada oración ya agrupada.
    Devuelve (sentences, discarded_count)."""
    sentences = []
    discarded = 0

    buffer_parts = []
    buffer_start = None
    buffer_end = None

    for block in blocks:
        cleaned = clean_text(block["raw_text"])

        if not cleaned:
            discarded += 1
            continue

        if buffer_start is None:
            buffer_start = block["start"]

        buffer_parts.append(cleaned)
        buffer_end = block["end"]

        if SENTENCE_END_RE.search(cleaned):
            combined = " ".join(buffer_parts)
            trimmed_start, trimmed_end = apply_boundary_trim(
                buffer_start, buffer_end, trim_start, trim_end
            )
            sentences.append({
                "start": trimmed_start,
                "end": trimmed_end,
                "text": normalize_case(combined),
            })
            buffer_parts = []
            buffer_start = None

    # Flush de lo que quede sin cerrar al final del archivo
    if buffer_parts:
        combined = " ".join(buffer_parts)
        trimmed_start, trimmed_end = apply_boundary_trim(
            buffer_start, buffer_end, trim_start, trim_end
        )
        sentences.append({
            "start": trimmed_start,
            "end": trimmed_end,
            "text": normalize_case(combined),
        })

    return sentences, discarded


def apply_global_shift(sentences, shift):
    """Aplica el mismo desplazamiento a TODOS los límites de oración,
    EXCEPTO el inicio de la primera línea, que queda anclado sin modificar
    (ya que se asume verificado como correcto contra el audio real).

    shift: segundos a SUMAR. Usa un valor NEGATIVO para adelantar/restar
           tiempo (ej. -0.4 para restar 400ms a todo salvo el primer inicio).

    Ejemplo con shift=-0.4:
        Línea 1: start SIN CAMBIO           | end -= 0.4
        Línea 2: start -= 0.4               | end -= 0.4
        Línea 3: start -= 0.4               | end -= 0.4
        ...
    """
    if not sentences or shift == 0.0:
        return sentences

    shifted = []
    for i, s in enumerate(sentences):
        new_start = s["start"] if i == 0 else s["start"] + shift
        new_end = s["end"] + shift
        shifted.append({
            "start": new_start,
            "end": new_end,
            "text": s["text"],
        })
    return shifted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("srt_path", help="Ruta al archivo .srt de entrada")
    parser.add_argument("-o", "--output", default="preview.csv",
                         help="Ruta del CSV de salida (default: preview.csv)")
    parser.add_argument("--min-duration", type=float, default=0.0,
                         help="Descarta oraciones más cortas que N segundos (default: 0, sin filtro)")
    parser.add_argument("--min-words", type=int, default=0,
                         help="Descarta oraciones con menos de N palabras (default: 0, sin filtro)")
    parser.add_argument("--offset", type=float, default=0.0,
                         help="Segundos a sumar a todos los tiempos, para corregir un desfase "
                              "CONSTANTE entre subtítulo y audio (default: 0.0)")
    parser.add_argument("--scale", type=float, default=1.0,
                         help="Factor multiplicativo aplicado antes del offset, para corregir "
                              "un desfase que crece con el tiempo por diferencia de framerate "
                              "(default: 1.0, sin corrección)")
    parser.add_argument("--trim-start", type=float, default=0.0,
                         help="Segundos a recortar al INICIO de cada oración de forma "
                              "independiente y proporcional a su duración (default: 0.0, "
                              "desactivado). No lo combines con --shift salvo que sepas "
                              "bien lo que haces.")
    parser.add_argument("--trim-end", type=float, default=0.0,
                         help="Segundos a recortar al FINAL de cada oración, igual que "
                              "--trim-start pero al final (default: 0.0, desactivado).")
    parser.add_argument("--shift", type=float, default=0.0,
                         help="Segundos a SUMAR a todos los límites de oración, EXCEPTO el "
                              "inicio de la primera línea (que queda anclado sin modificar). "
                              "Usa un valor negativo para restar tiempo, ej. -0.4 para restar "
                              "400ms a todo salvo el primer inicio (default: 0.0)")
    args = parser.parse_args()

    blocks = parse_srt_blocks(args.srt_path, offset=args.offset, scale=args.scale)
    sentences, discarded = group_into_sentences(
        blocks, trim_start=args.trim_start, trim_end=args.trim_end
    )
    sentences = apply_global_shift(sentences, args.shift)

    total_before_filter = len(sentences)
    filtered = []
    skipped_by_filter = 0

    for s in sentences:
        duration = s["end"] - s["start"]
        word_count = len(s["text"].split())
        if duration < args.min_duration or word_count < args.min_words:
            skipped_by_filter += 1
            continue
        filtered.append(s)

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["line_number", "start", "end", "duration_sec", "text"])
        for i, s in enumerate(filtered, start=1):
            duration = round(s["end"] - s["start"], 3)
            writer.writerow([
                i,
                seconds_to_timestamp(s["start"]),
                seconds_to_timestamp(s["end"]),
                duration,
                s["text"],
            ])

    print(f"Bloques SRT leídos:              {len(blocks)}")
    print(f"Bloques descartados (sin texto): {discarded}  (solo efectos de sonido)")
    print(f"Oraciones agrupadas:             {total_before_filter}")
    if args.min_duration > 0 or args.min_words > 0:
        print(f"Descartadas por filtro (--min-duration/--min-words): {skipped_by_filter}")
    print(f"Oraciones finales en CSV:        {len(filtered)}")
    print(f"\nCSV generado: {args.output}")


if __name__ == "__main__":
    main()