#!/usr/bin/env python3
"""
core/clip_engine.py

Lógica de corte de clips (vídeo .webm + audio .mp3), traducción con DeepL
y generación del .tsv (Fase 2 del pipeline Anki-Video). Extraída de
cut_clips.py para poder reutilizarla tanto desde la CLI como, en la
próxima fase, desde la GUI.

No cambia ningún comportamiento respecto a la versión anterior (v3) para
el flujo por lote (process_episode). Se agrega cut_single_clip(), pensada
para el corte interactivo "uno por uno" que usará la GUI: en vez de
decodificar el episodio completo en una sola pasada, usa un salto rápido
(-ss antes de -i) + filtro trim/atrim para precisión exacta sin tener que
procesar todo el archivo — ideal quando solo necesitas UN clip ya mismo.
"""

import csv
import json
import os
import re
import subprocess
import sys

from core.naming import clip_audio_filename, clip_video_filename


MIN_DURATION = 0.05  # segundos; por debajo de esto una línea es inválida


class BatchCancelToken:
    """Token compartido para cancelar un run_batch() en curso desde la GUI."""

    def __init__(self):
        self.cancelled = False
        self._process = None

    def request_cancel(self):
        self.cancelled = True
        proc = self._process
        if proc is not None and proc.poll() is None:
            proc.terminate()


# ---------------------------------------------------------------------------
# Título del episodio (para nombrar el TSV)
# ---------------------------------------------------------------------------

def detect_video_title(video_path):
    """Lee el metadato 'title' del contenedor (.mkv/.mp4) vía ffprobe.
    Devuelve el string tal cual, o None si no existe o falla."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format_tags=title",
             "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True, text=True, timeout=15,
        )
        title = result.stdout.strip()
        return title if title else None
    except Exception:
        return None


def extract_episode_title(raw_title):
    """De un título tipo 'Spawn - S01E01 - Burning Visions' extrae solo
    'Burning Visions' (la última parte tras ' - '). Si no sigue ese
    patrón, devuelve el título completo tal cual."""
    if not raw_title:
        return None
    parts = [p.strip() for p in raw_title.split(" - ")]
    return parts[-1] if len(parts) > 1 else raw_title.strip()


def sanitize_filename_component(text):
    """Convierte un título libre en algo seguro para usar en un nombre de
    archivo: espacios -> guion bajo, quita caracteres problemáticos."""
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "_", text.strip())
    return text


# ---------------------------------------------------------------------------
# Traducción con caché local (DeepL / Gemini)
# ---------------------------------------------------------------------------

def _is_legacy_flat_cache(raw: dict) -> bool:
    return bool(raw) and all(isinstance(v, str) for v in raw.values())


def normalize_translation_cache(raw: dict | None) -> dict[str, dict[str, str]]:
    if not raw:
        return {"deepl": {}, "gemini": {}}
    if "deepl" in raw or "gemini" in raw:
        return {
            "deepl": dict(raw.get("deepl") or {}),
            "gemini": dict(raw.get("gemini") or {}),
        }
    if _is_legacy_flat_cache(raw):
        return {"deepl": dict(raw), "gemini": {}}
    return {"deepl": {}, "gemini": {}}


def load_translation_cache(cache_path):
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            raw = json.load(f)
        return normalize_translation_cache(raw)
    return {"deepl": {}, "gemini": {}}


def save_translation_cache(cache_path, cache):
    normalized = normalize_translation_cache(cache)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)


def lookup_cached_translation(cache, provider: str, text: str) -> str | None:
    bucket = cache.get(provider, {})
    val = bucket.get(text)
    return val if val else None


def translate_texts(texts, api_key, target_lang, cache_path):
    """Traduce una lista de textos usando DeepL, reutilizando una caché
    local (JSON) para no volver a traducir líneas ya traducidas antes.

    Devuelve (traducciones_por_texto, textos_fallidos). Las traducciones
    vacías no se guardan en caché."""
    import deepl

    cache = load_translation_cache(cache_path)
    bucket = cache["deepl"]
    to_translate = [t for t in dict.fromkeys(texts) if not bucket.get(t)]
    failed: list[str] = []

    if to_translate:
        try:
            translator = deepl.Translator(api_key)
            print(f"Traduciendo {len(to_translate)} línea(s) nueva(s) con DeepL "
                  f"(ya en caché: {len(set(texts)) - len(to_translate)})...")
            results = translator.translate_text(to_translate, target_lang=target_lang)
            cache_dirty = False
            for original, result in zip(to_translate, results):
                translation = (result.text or "").strip()
                if translation:
                    bucket[original] = translation
                    cache_dirty = True
                else:
                    failed.append(original)
                    if original in bucket:
                        del bucket[original]
                        cache_dirty = True
            if cache_dirty:
                cache["deepl"] = bucket
                save_translation_cache(cache_path, cache)
        except Exception as e:
            raise RuntimeError(f"DeepL: {e}") from e
    else:
        print("Todas las líneas ya estaban traducidas en la caché, no se llamó a la API.")

    return {t: bucket.get(t, "") for t in texts}, failed


_GEMINI_NUMBERED_LINE_RE = re.compile(r"^\s*(\d+)\.\s*(.+)$", re.MULTILINE)


def _gemini_target_language_label(target_lang: str) -> str:
    lang = (target_lang or "ES").upper()
    if lang.startswith("ES"):
        return "español latinoamericano neutro"
    return target_lang


def _gemini_translation_instructions(target_lang: str) -> str:
    lang_label = _gemini_target_language_label(target_lang)
    return (
        f"Traduce cada línea al {lang_label} con tono coloquial de diálogo "
        f"hablado (no estilo de doblaje de España). "
        f"Preserva etiquetas HTML como <i></i> sin traducir el marcado HTML. "
        f"No añadas explicaciones ni texto extra: responde solo con las "
        f"traducciones numeradas en el mismo formato de entrada."
    )


def _format_numbered_texts(texts: list[str]) -> str:
    return "\n".join(f"{i + 1}. {text}" for i, text in enumerate(texts))


def _parse_gemini_numbered_response(response_text: str, count: int) -> list[str]:
    matches: dict[int, str] = {}
    for match in _GEMINI_NUMBERED_LINE_RE.finditer(response_text.strip()):
        idx = int(match.group(1))
        matches[idx] = match.group(2).strip()
    return [matches.get(i + 1, "") for i in range(count)]


def _gemini_response_text(response) -> str:
    return getattr(response, "text", "") or ""


def _translate_gemini_batch(client, texts: list[str], target_lang: str) -> list[str]:
    prompt = (
        f"{_gemini_translation_instructions(target_lang)}\n\n"
        f"{_format_numbered_texts(texts)}"
    )
    response = client.models.generate_content(model=_GEMINI_MODEL, contents=prompt)
    response_text = _gemini_response_text(response)
    return _parse_gemini_numbered_response(response_text, len(texts))


def _translate_gemini_one_by_one(client, texts: list[str], target_lang: str) -> list[str]:
    translations = []
    instructions = _gemini_translation_instructions(target_lang)
    for text in texts:
        prompt = f"{instructions}\n\nTraduce esta única línea:\n{text}"
        response = client.models.generate_content(model=_GEMINI_MODEL, contents=prompt)
        response_text = _gemini_response_text(response)
        translations.append(response_text.strip())
    return translations


_GEMINI_MODEL = "gemini-flash-latest"


def _raise_gemini_error(exc: Exception) -> None:
    if isinstance(exc, RuntimeError) and str(exc).startswith("Gemini:"):
        raise exc
    msg = str(exc).lower()
    exc_name = type(exc).__name__.lower()
    model_unavailable = (
        "not found" in msg
        or "404" in msg
        or "does not exist" in msg
        or "invalid model" in msg
        or "unknown model" in msg
        or "modelnotfound" in exc_name
        or ("model" in msg and "not" in msg)
    )
    if model_unavailable:
        raise RuntimeError(
            "Gemini: El modelo de Gemini configurado no está disponible para tu "
            "API key; verifica el nombre del modelo en Google AI Studio"
        ) from exc
    raise RuntimeError(f"Gemini: {exc}") from exc


def translate_texts_gemini(texts, api_key, target_lang, cache_path):
    """Traduce una lista de textos usando Gemini, reutilizando caché local.

    Devuelve (traducciones_por_texto, textos_fallidos). Las traducciones
    vacías no se guardan en caché."""
    try:
        from google import genai
    except ImportError as e:
        raise RuntimeError(
            "Gemini: falta el paquete google-genai. "
            "Instálalo con: pip install google-genai"
        ) from e

    try:
        cache = load_translation_cache(cache_path)
        bucket = cache["gemini"]
        to_translate = [t for t in dict.fromkeys(texts) if not bucket.get(t)]
        failed: list[str] = []

        if to_translate:
            client = genai.Client(api_key=api_key)
            print(f"Traduciendo {len(to_translate)} línea(s) nueva(s) con Gemini "
                  f"(ya en caché: {len(set(texts)) - len(to_translate)})...")
            parsed = _translate_gemini_batch(client, to_translate, target_lang)
            if len([p for p in parsed if p]) != len(to_translate):
                print("Gemini: respuesta batch incompleta, traduciendo línea a línea...")
                parsed = _translate_gemini_one_by_one(client, to_translate, target_lang)
            cache_dirty = False
            for original, translation in zip(to_translate, parsed):
                translation = (translation or "").strip()
                if translation:
                    bucket[original] = translation
                    cache_dirty = True
                else:
                    failed.append(original)
                    if original in bucket:
                        del bucket[original]
                        cache_dirty = True
            if cache_dirty:
                cache["gemini"] = bucket
                save_translation_cache(cache_path, cache)
        else:
            print("Todas las líneas ya estaban traducidas en la caché, no se llamó a la API.")

        return {t: bucket.get(t, "") for t in texts}, failed
    except Exception as e:
        _raise_gemini_error(e)


# ---------------------------------------------------------------------------
# CSV -> ventanas de tiempo
# ---------------------------------------------------------------------------

def parse_timestamp(ts):
    """'HH:MM:SS.mmm' -> segundos (float)."""
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def load_sentences_from_csv(csv_path):
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
        windows.append(
            compute_padded_window(
                s["start"],
                s["end"],
                padding_start=padding,
                padding_end=padding,
                prev_end=prev_end,
                next_start=next_start,
            )
        )
    return windows


def compute_padded_window(
    start,
    end,
    *,
    padding_start=0.0,
    padding_end=0.0,
    prev_end=None,
    next_start=None,
):
    """Ventana de corte con margen, sin invadir la línea anterior/siguiente."""
    padded_start = start - padding_start
    if padded_start < 0:
        padded_start = 0.0
    if prev_end is not None:
        padded_start = max(padded_start, prev_end)

    padded_end = end + padding_end
    if next_start is not None:
        padded_end = min(padded_end, next_start)

    return padded_start, padded_end


# ---------------------------------------------------------------------------
# Corte por LOTE: una sola pasada continua para todo el episodio
# ---------------------------------------------------------------------------

def build_single_pass_command(video_path, jobs, width, height, crf,
                               webm_audio_bitrate, mp3_bitrate, max_time,
                               audio_track=0, video_track=0):
    """jobs: lista de dicts con:
        index, start, end, need_video, need_audio, video_path, audio_path
    Construye UN comando ffmpeg que decodifica el vídeo una sola vez y
    produce todos los .webm y .mp3 necesarios de esa misma pasada, usando
    split/asplit + trim/atrim. Vídeo y audio de una misma línea usan
    exactamente el mismo start/end.

    audio_track/video_track: índice RELATIVO de la pista a usar (0 = la
    primera pista de ese tipo, 1 = la segunda, etc.) — útil cuando el
    archivo trae audio en varios idiomas. Usa inspect_media.py para ver
    qué pistas hay disponibles antes de elegir el índice.
    """
    video_jobs = [j for j in jobs if j["need_video"]]
    audio_jobs = [j for j in jobs if j["need_audio"]]

    total_audio_branches = len(video_jobs) + len(audio_jobs)
    filter_parts = []
    map_args = []

    audio_labels = [f"a{n}" for n in range(total_audio_branches)]
    if audio_labels:
        filter_parts.append(
            f"[0:a:{audio_track}]asplit=" + str(len(audio_labels)) +
            "".join(f"[{lbl}]" for lbl in audio_labels)
        )
    label_pos = 0

    if video_jobs:
        vlabels = [f"v{j['index']}" for j in video_jobs]
        filter_parts.append(
            f"[0:v:{video_track}]split=" + str(len(video_jobs)) +
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


def validate_and_build_jobs(sentences, windows, series_name, episode_label,
                             output_dir, want_video, want_audio,
                             overwrite, start_index=1, episode_title=""):
    """Recorre sentences+windows y arma:
        - jobs: lo que realmente hay que generar en esta corrida
        - tsv_rows: (id, text, video_filename, audio_filename, episode_label, episode_title)
          para TODAS las líneas (independiente de si se generan en esta corrida)
        - video_skipped / audio_skipped: contadores
        - invalid_lines: líneas con end<=start, excluidas de 'jobs'
    """
    jobs = []
    tsv_rows = []
    video_skipped = 0
    audio_skipped = 0
    invalid_lines = []

    for offset, (sentence, (start, end)) in enumerate(zip(sentences, windows)):
        i = start_index + offset
        video_filename = clip_video_filename(series_name, episode_label, i)
        audio_filename = clip_audio_filename(series_name, episode_label, i)
        video_path = os.path.join(output_dir, video_filename)
        audio_path = os.path.join(output_dir, audio_filename)

        tsv_rows.append((i, sentence["text"], video_filename, audio_filename,
                          episode_label, episode_title))

        if end - start < MIN_DURATION:
            invalid_lines.append((i, start, end, sentence["text"]))
            continue

        need_video = want_video and (overwrite or not os.path.exists(video_path))
        need_audio = want_audio and (overwrite or not os.path.exists(audio_path))

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

    return jobs, tsv_rows, video_skipped, audio_skipped, invalid_lines


def run_batch(video_path, jobs, width, height, crf, audio_bitrate, mp3_bitrate,
              audio_track=0, video_track=0, cancel_token=None):
    """Ejecuta el comando de pasada única para 'jobs'. Devuelve
    (video_generated, video_errors, audio_generated, audio_errors, error_message).

    cancel_token: BatchCancelToken opcional; request_cancel() termina ffmpeg."""
    video_generated = video_errors = 0
    audio_generated = audio_errors = 0
    error_message = None

    if not jobs:
        return video_generated, video_errors, audio_generated, audio_errors, error_message

    if cancel_token is not None and cancel_token.cancelled:
        return video_generated, video_errors, audio_generated, audio_errors, "Cancelado por el usuario."

    max_time = max(j["end"] for j in jobs) + 1.0
    cmd = build_single_pass_command(
        video_path, jobs, width, height, crf, audio_bitrate, mp3_bitrate, max_time,
        audio_track=audio_track, video_track=video_track,
    )
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if cancel_token is not None:
        cancel_token._process = process
    _stdout, stderr = process.communicate()

    if cancel_token is not None and cancel_token.cancelled:
        return video_generated, video_errors, audio_generated, audio_errors, "Cancelado por el usuario."

    if process.returncode != 0:
        error_message = stderr.strip()[-2000:]
        return video_generated, video_errors, audio_generated, audio_errors, error_message

    for j in jobs:
        if j["need_video"]:
            if os.path.exists(j["video_path"]) and os.path.getsize(j["video_path"]) > 0:
                video_generated += 1
            else:
                video_errors += 1
        if j["need_audio"]:
            if os.path.exists(j["audio_path"]) and os.path.getsize(j["audio_path"]) > 0:
                audio_generated += 1
            else:
                audio_errors += 1

    return video_generated, video_errors, audio_generated, audio_errors, error_message


def write_anki_tsv(tsv_path, tsv_rows, translations):
    """Escribe el TSV con los 9 campos de la nota Anki:
    id | episode | episode_title | video | video_reference | video_audio |
    english_dialogs | spanish_dialogues | notes (vacío)"""
    with open(tsv_path, "w", encoding="utf-8", newline="") as f:
        for i, text, video_filename, audio_filename, episode_label, episode_title in tsv_rows:
            translation = translations.get(text, "")
            video_field = video_filename
            video_reference_field = f"[sound:{video_filename}]"
            video_audio_field = f"[sound:{audio_filename}]"
            notes_field = ""
            f.write(
                f"{i:04d}\t{episode_label}\t{episode_title}\t{video_field}\t"
                f"{video_reference_field}\t{video_audio_field}\t{text}\t"
                f"{translation}\t{notes_field}\n"
            )


def compute_media_sizes(tsv_rows, output_dir):
    """Devuelve (video_size_mb, audio_size_mb) sumando lo que exista en disco."""
    def total_size(paths):
        return sum(os.path.getsize(p) for p in paths if os.path.exists(p))

    video_size_mb = total_size(
        os.path.join(output_dir, vf) for _, _, vf, _, _, _ in tsv_rows
    ) / (1024 * 1024)
    audio_size_mb = total_size(
        os.path.join(output_dir, af) for _, _, _, af, _, _ in tsv_rows
    ) / (1024 * 1024)
    return video_size_mb, audio_size_mb


# ---------------------------------------------------------------------------
# Corte INDIVIDUAL bajo demanda (para la futura GUI)
# ---------------------------------------------------------------------------

def cut_single_clip(video_path, start, end, output_path, media="both",
                     width=640, height=480, crf=32,
                     webm_audio_bitrate="96k", mp3_audio_bitrate="128k",
                     audio_track=0, video_track=0):
    """Corta UN solo clip usando salto rápido (-ss antes de -i) + trim/atrim
    para precisión exacta, sin decodificar el episodio completo. Pensado
    para el botón "Cortar" de la GUI interactiva (Fase 2), donde el usuario
    corta de a uno mientras revisa la lista, no en lote.

    media: "video" -> genera solo el .webm en output_path
           "audio" -> genera solo el .mp3 en output_path
           "both"  -> requiere que output_path sea la ruta SIN extensión;
                      genera output_path+".webm" y output_path+".mp3"

    audio_track/video_track: índice relativo de la pista a usar (ver
    build_single_pass_command).

    Devuelve (success: bool, stderr: str).
    """
    duration = end - start
    coarse_seek = max(0.0, start - 10.0)
    fine_seek = start - coarse_seek

    if media == "video":
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{coarse_seek:.3f}", "-i", video_path,
            "-filter_complex",
            (
                f"[0:v:{video_track}]trim=start={fine_seek:.3f}:duration={duration:.3f},"
                f"setpts=PTS-STARTPTS,scale={width}:{height}[vout];"
                f"[0:a:{audio_track}]atrim=start={fine_seek:.3f}:duration={duration:.3f},"
                f"asetpts=PTS-STARTPTS[aout]"
            ),
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libvpx-vp9", "-crf", str(crf), "-b:v", "0",
            "-deadline", "good", "-cpu-used", "3",
            "-c:a", "libopus", "-b:a", webm_audio_bitrate,
            "-loglevel", "error",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0, result.stderr

    elif media == "audio":
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{coarse_seek:.3f}", "-i", video_path,
            "-filter_complex",
            (
                f"[0:a:{audio_track}]atrim=start={fine_seek:.3f}:duration={duration:.3f},"
                f"asetpts=PTS-STARTPTS[aout]"
            ),
            "-map", "[aout]",
            "-c:a", "libmp3lame", "-b:a", mp3_audio_bitrate,
            "-loglevel", "error",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0, result.stderr

    elif media == "both":
        ok_v, err_v = cut_single_clip(
            video_path, start, end, output_path + ".webm", media="video",
            width=width, height=height, crf=crf, webm_audio_bitrate=webm_audio_bitrate,
            audio_track=audio_track, video_track=video_track,
        )
        ok_a, err_a = cut_single_clip(
            video_path, start, end, output_path + ".mp3", media="audio",
            mp3_audio_bitrate=mp3_audio_bitrate, audio_track=audio_track,
        )
        return (ok_v and ok_a), (err_v + err_a)

    else:
        raise ValueError(f"media inválido: {media!r} (usa 'video', 'audio' o 'both')")


def _test_empty_gemini_translation_not_cached() -> None:
    """Traducción vacía no debe quedar en caché; un reintento válido sí."""
    import tempfile
    from unittest.mock import MagicMock, patch

    sample_text = "Hello world!"
    with tempfile.TemporaryDirectory() as tmp:
        cache_path = os.path.join(tmp, "translations_cache.json")
        save_translation_cache(cache_path, {"deepl": {}, "gemini": {sample_text: ""}})

        mock_client = MagicMock()
        empty_response = MagicMock(text="")
        good_response = MagicMock(text="Hola mundo!")
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client

        import types
        mock_google = types.ModuleType("google")
        mock_google.genai = mock_genai

        with patch.dict(sys.modules, {"google": mock_google, "google.genai": mock_genai}):
            mock_client.models.generate_content.return_value = empty_response
            results, failed = translate_texts_gemini(
                [sample_text], "fake-key", "ES", cache_path
            )
            assert sample_text in failed, failed
            assert results[sample_text] == ""
            cache = load_translation_cache(cache_path)
            assert sample_text not in cache["gemini"], cache["gemini"]

            mock_client.models.generate_content.return_value = good_response
            results, failed = translate_texts_gemini(
                [sample_text], "fake-key", "ES", cache_path
            )
            assert failed == [], failed
            assert results[sample_text] == "Hola mundo!"
            cache = load_translation_cache(cache_path)
            assert cache["gemini"][sample_text] == "Hola mundo!"


if __name__ == "__main__":
    _test_empty_gemini_translation_not_cached()
    print("OK: empty Gemini translations are not cached")