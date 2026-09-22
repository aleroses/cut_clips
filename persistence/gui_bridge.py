"""Conversión entre el estado de gui_app.py y persistence.models."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

from core.naming import clip_audio_filename, clip_basename, clip_video_filename, format_episode_label
from persistence.models import Clip, ClipStatus, Episode, Project, SubtitleCue, TranslationConfig
from ui.parser_options_widget import ParserOptions

GUI_STATUS_TO_CLIP: dict[str, ClipStatus] = {
    "pending": ClipStatus.PENDING,
    "preview": ClipStatus.PREVIEW,
    "exported": ClipStatus.GENERATED,
    "outdated": ClipStatus.OUTDATED,
    "cutting": ClipStatus.MODIFIED,
}

CLIP_STATUS_TO_GUI: dict[ClipStatus, str] = {
    ClipStatus.PENDING: "pending",
    ClipStatus.MODIFIED: "pending",
    ClipStatus.PREVIEW: "preview",
    ClipStatus.GENERATED: "exported",
    ClipStatus.OUTDATED: "outdated",
    ClipStatus.ERROR: "pending",
}


def guess_series_name(video_path: str) -> str:
    """Nombre de serie inferido a partir del archivo de vídeo."""
    base = os.path.splitext(os.path.basename(video_path))[0]
    cleaned = re.sub(r"[Ss]\d{1,2}[Ee]\d{1,2}.*$", "", base)
    cleaned = re.sub(r"[Ee]p(?:isode)?[\s_-]*\d+.*$", "", cleaned)
    cleaned = cleaned.strip(" -_.")
    return cleaned or "Series"


def parse_season_episode(raw_title: str | None, *, default_season: int = 1) -> tuple[int, int]:
    """Extrae temporada y episodio de un título tipo S01E01."""
    if raw_title:
        match = re.search(r"[Ss](\d{1,2})[\s_.-]*[Ee](\d{1,2})", raw_title)
        if match:
            return int(match.group(1)), int(match.group(2))
        match = re.search(r"[Ee]p(?:isode)?[\s_.-]*(\d{1,2})", raw_title)
        if match:
            return default_season, int(match.group(1))
    return default_season, 1


def parser_options_to_dict(options: ParserOptions) -> dict[str, Any]:
    return options.as_generate_kwargs()


def parser_options_from_dict(data: dict[str, Any]) -> ParserOptions:
    return ParserOptions(
        offset=float(data.get("offset", 0.0)),
        scale=float(data.get("scale", 1.0)),
        trim_start=float(data.get("trim_start", 0.0)),
        trim_end=float(data.get("trim_end", 0.0)),
        shift=float(data.get("shift", 0.0)),
        min_duration=float(data.get("min_duration", 0.0)),
        min_words=int(data.get("min_words", 0)),
        language=str(data.get("language", "en")),
    )


def cues_to_subtitle_cues(cue_map: dict[int, dict]) -> list[SubtitleCue]:
    cues = []
    for index in sorted(cue_map):
        cue = cue_map[index]
        cues.append(
            SubtitleCue(
                index=int(cue["index"]),
                start=float(cue["start"]),
                end=float(cue["end"]),
                text=str(cue["text"]),
            )
        )
    return cues


def subtitle_cues_to_map(subtitles: list[SubtitleCue]) -> dict[int, dict]:
    return {
        cue.index: {
            "index": cue.index,
            "start": cue.start,
            "end": cue.end,
            "text": cue.text,
        }
        for cue in subtitles
    }


def build_segment_fingerprint(
    seg: dict,
    *,
    video_path: str,
    audio_track: int,
    video_track: int,
    padding_start: float | None = None,
    padding_end: float | None = None,
    width: int = 640,
    height: int = 480,
    crf: int = 32,
) -> dict[str, Any]:
    """Fingerprint actual de un segmento GUI (misma lógica que Clip.compute_fingerprint)."""
    clip = Clip(
        id=int(seg["id"]),
        internal_index=0,
        text=str(seg.get("text", "")),
        start=float(seg.get("start", 0.0)),
        end=float(seg.get("end", 0.0)),
        padding_start=float(
            padding_start if padding_start is not None else seg.get("padding_start", 0.0)
        ),
        padding_end=float(
            padding_end if padding_end is not None else seg.get("padding_end", 0.0)
        ),
    )
    return clip.compute_fingerprint(
        video_path=video_path or "",
        audio_track=audio_track,
        video_track=video_track,
        width=width,
        height=height,
        crf=crf,
    )


def apply_outdated_status(seg: dict, current_fingerprint: dict[str, Any]) -> bool:
    """Actualiza status exported/outdated según fingerprint. Devuelve True si quedó outdated."""
    if seg.get("status") not in ("exported", "outdated"):
        return False
    stored = seg.get("generation_fingerprint")
    if not stored:
        return False
    if stored != current_fingerprint:
        seg["status"] = "outdated"
        return True
    if seg["status"] == "outdated":
        seg["status"] = "exported"
    return False


def clip_output_paths(
    series_name: str,
    episode_label: str,
    clip_id: int,
    output_dir: str,
) -> tuple[str, str, str]:
    """Rutas completas (webm, mp3, basename sin extensión) con naming CLI."""
    video_name = clip_video_filename(series_name, episode_label, clip_id)
    audio_name = clip_audio_filename(series_name, episode_label, clip_id)
    base = clip_basename(series_name, episode_label, clip_id)
    return (
        os.path.join(output_dir, video_name),
        os.path.join(output_dir, audio_name),
        os.path.join(output_dir, base),
    )


def segment_to_clip(
    seg: dict,
    *,
    internal_index: int,
    output_dir: str,
    series_name: str,
    episode_label: str,
    padding_start: float = 0.0,
    padding_end: float = 0.0,
) -> Clip | None:
    status_key = seg.get("status")
    if status_key == "deleted":
        return None
    clip_status = GUI_STATUS_TO_CLIP.get(status_key, ClipStatus.PENDING)

    clip_id = int(seg["id"])
    webm_path, mp3_path, _ = clip_output_paths(
        series_name, episode_label, clip_id, output_dir
    )

    clip = Clip(
        id=clip_id,
        internal_index=internal_index,
        subtitle_indices=[int(i) for i in seg.get("cue_indices", [])],
        text=str(seg.get("text", "")),
        start=float(seg.get("start", 0.0)),
        end=float(seg.get("end", 0.0)),
        padding_start=float(seg.get("padding_start", padding_start)),
        padding_end=float(seg.get("padding_end", padding_end)),
        status=clip_status,
    )
    if clip_status in (ClipStatus.GENERATED, ClipStatus.OUTDATED):
        clip.video_path = webm_path
        clip.audio_path = mp3_path
    clip.generation_fingerprint = dict(seg.get("generation_fingerprint", {}))
    return clip


def clip_to_segment(clip: Clip, extras: dict[str, Any] | None = None) -> dict:
    extras = extras or {}
    status = CLIP_STATUS_TO_GUI.get(clip.status, "pending")
    seg = {
        "id": clip.id,
        "start": clip.start,
        "end": clip.end,
        "text": clip.text,
        "status": status,
        "cue_indices": list(clip.subtitle_indices),
        "padding_start": clip.padding_start,
        "padding_end": clip.padding_end,
    }
    if status == "preview":
        seg["preview_start"] = extras.get("preview_start", clip.start)
        seg["preview_end"] = extras.get("preview_end", clip.end)
    if clip.generation_fingerprint:
        seg["generation_fingerprint"] = dict(clip.generation_fingerprint)
    return seg


def build_project_from_gui(
    *,
    series_name: str,
    season: int,
    episode_num: int,
    video_path: str | None,
    episode_title: str,
    subtitle_path: str | None,
    subtitle_track_index: int | None,
    subtitle_language: str,
    audio_track: int,
    video_track: int,
    media_summary: dict | None,
    parser_options: ParserOptions,
    cue_map: dict[int, dict],
    segments: list[dict],
    translate_enabled: bool,
    last_clip_id: int,
    root_dir: str,
    padding_start: float = 0.0,
    padding_end: float = 0.0,
) -> Project:
    output_dir = "output_files"
    if video_path:
        output_dir = os.path.join(os.path.dirname(video_path), "output_files")

    episode_label = format_episode_label(season, episode_num)
    clips: list[Clip] = []
    clips_extra: dict[str, dict[str, float]] = {}
    internal_index = 0
    for seg in segments:
        clip = segment_to_clip(
            seg,
            internal_index=internal_index,
            output_dir=output_dir,
            series_name=series_name,
            episode_label=episode_label,
            padding_start=padding_start,
            padding_end=padding_end,
        )
        if clip is None:
            continue
        clips.append(clip)
        if seg.get("status") == "preview":
            clips_extra[str(seg["id"])] = {
                "preview_start": float(seg.get("preview_start", seg["start"])),
                "preview_end": float(seg.get("preview_end", seg["end"])),
            }
        internal_index += 1

    media_info = dict(media_summary or {})
    media_info["gui_parser_options"] = parser_options_to_dict(parser_options)
    if clips_extra:
        media_info["gui_clips_extra"] = clips_extra

    episode = Episode(
        video_path=video_path or "",
        season=season,
        episode=episode_num,
        episode_title=episode_title,
        subtitle_path=subtitle_path or "",
        subtitle_track_index=subtitle_track_index,
        subtitle_language=subtitle_language,
        audio_track=audio_track,
        video_track=video_track,
        padding_start=padding_start,
        padding_end=padding_end,
        media_info=media_info,
        subtitles=cues_to_subtitle_cues(cue_map),
        clips=clips,
        translation=TranslationConfig(
            provider="deepl" if translate_enabled else "none",
            target_lang="ES",
        ),
        output_dir=output_dir,
    )

    return Project(
        series_name=series_name,
        root_dir=root_dir,
        last_clip_id=last_clip_id,
        episodes=[episode],
    )


@dataclass
class LoadedGuiState:
    series_name: str
    season: int
    episode_num: int
    video_path: str | None
    episode_title: str
    subtitle_path: str | None
    subtitle_track_index: int | None
    subtitle_language: str
    audio_track: int
    video_track: int
    media_summary: dict | None
    parser_options: ParserOptions
    cue_map: dict[int, dict]
    segments: list[dict]
    next_id: int
    translate_enabled: bool
    root_dir: str
    padding_start: float
    padding_end: float


def load_gui_state_from_project(project: Project) -> LoadedGuiState:
    episode = project.current_episode()
    if episode is None:
        raise ValueError("El proyecto no contiene episodios.")

    media_info = dict(episode.media_info or {})
    parser_options = parser_options_from_dict(media_info.pop("gui_parser_options", {}))
    clips_extra = media_info.pop("gui_clips_extra", {})

    cue_map = subtitle_cues_to_map(episode.subtitles)
    segments = []
    for clip in sorted(episode.clips, key=lambda c: c.internal_index):
        extras = clips_extra.get(str(clip.id), {})
        segments.append(clip_to_segment(clip, extras))

    next_id = project.last_clip_id + 1
    if segments:
        next_id = max(next_id, max(s["id"] for s in segments) + 1)

    return LoadedGuiState(
        series_name=project.series_name,
        season=episode.season,
        episode_num=episode.episode,
        video_path=episode.video_path or None,
        episode_title=episode.episode_title,
        subtitle_path=episode.subtitle_path or None,
        subtitle_track_index=episode.subtitle_track_index,
        subtitle_language=episode.subtitle_language,
        audio_track=episode.audio_track,
        video_track=episode.video_track,
        media_summary=media_info or None,
        parser_options=parser_options,
        cue_map=cue_map,
        segments=segments,
        next_id=next_id,
        translate_enabled=episode.translation.provider != "none",
        root_dir=project.root_dir,
        padding_start=episode.padding_start,
        padding_end=episode.padding_end,
    )
