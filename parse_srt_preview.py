#!/usr/bin/env python3
"""
parse_srt_preview.py (v3 - envoltorio delgado sobre core/subtitle_parser.py)

Paso 1 del pipeline Anki-Video: parsea un .srt SDH, agrupa fragmentos de
subtítulo en oraciones completas y filtra bloques que son solo efectos de
sonido / etiquetas de hablante sin diálogo. NO corta vídeo todavía — solo
genera una tabla (CSV) para que revises que la agrupación es correcta.

Toda la lógica real vive ahora en core/subtitle_parser.py, para poder
reutilizarla desde la futura GUI. Este archivo solo maneja argumentos de
línea de comandos y el reporte en pantalla — el comportamiento es
idéntico al de la versión anterior.

Uso:
    python3 parse_srt_preview.py S01E01.srt -o S01E01_preview.csv
    python3 parse_srt_preview.py S01E01.srt -o S01E01_preview.csv --shift -0.4
"""

import argparse
import os

from core.subtitle_parser import generate_sentences, write_sentences_csv


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
    parser.add_argument("--language", default="en",
                         help="Código de idioma del subtítulo (ej: en, es, fr, de, it, ja, "
                              "zh). Ajusta reglas de normalización específicas del idioma "
                              "(hoy: capitalización del pronombre 'I' solo en inglés, y el "
                              "espacio antes de puntuación se desactiva automáticamente para "
                              "francés). Default: en")
    args = parser.parse_args()

    result = generate_sentences(
        args.srt_path,
        offset=args.offset,
        scale=args.scale,
        trim_start=args.trim_start,
        trim_end=args.trim_end,
        shift=args.shift,
        min_duration=args.min_duration,
        min_words=args.min_words,
        language=args.language,
    )

    write_sentences_csv(args.output, result["sentences"])

    print(f"Bloques SRT leídos:              {result['total_blocks']}")
    print(f"Bloques descartados (sin texto): {result['discarded_blocks']}  (solo efectos de sonido)")
    print(f"Oraciones agrupadas:             {result['total_sentences']}")
    if args.min_duration > 0 or args.min_words > 0:
        print(f"Descartadas por filtro (--min-duration/--min-words): {result['skipped_by_filter']}")
    print(f"Oraciones finales en CSV:        {len(result['sentences'])}")
    print(f"\nCSV generado: {args.output}")


if __name__ == "__main__":
    main()