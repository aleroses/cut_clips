"""Funciones auxiliares para construir el modelo desde datos existentes."""

from __future__ import annotations

from core.naming import clip_audio_filename, clip_video_filename, format_episode_label
from persistence.models import Clip, ClipStatus, Episode, Project, SubtitleCue


def subtitles_from_parser_sentences(sentences: list[dict]) -> list[SubtitleCue]:
    """Convierte salida de generate_sentences()['sentences'] a SubtitleCue."""
    return [
        SubtitleCue(index=i, start=s["start"], end=s["end"], text=s["text"])
        for i, s in enumerate(sentences)
    ]


def clips_from_subtitles(
    subtitles: list[SubtitleCue],
    *,
    start_id: int = 1,
    padding_start: float = 0.0,
    padding_end: float = 0.0,
) -> list[Clip]:
    """Crea un clip por subtítulo/oración (estado inicial PENDING)."""
    clips = []
    for offset, cue in enumerate(subtitles):
        clip_id = start_id + offset
        clips.append(
            Clip(
                id=clip_id,
                internal_index=offset,
                subtitle_indices=[cue.index],
                text=cue.text,
                start=cue.start,
                end=cue.end,
                padding_start=padding_start,
                padding_end=padding_end,
                status=ClipStatus.PENDING,
            )
        )
    return clips


def assign_clip_output_paths(
    clips: list[Clip],
    *,
    series_name: str,
    episode_label: str,
    output_dir: str,
) -> None:
    """Rellena video_path/audio_path con nombres estándar (sin generar archivos)."""
    for clip in clips:
        video_name = clip_video_filename(series_name, episode_label, clip.id)
        audio_name = clip_audio_filename(series_name, episode_label, clip.id)
        clip.video_path = f"{output_dir}/{video_name}"
        clip.audio_path = f"{output_dir}/{audio_name}"


def new_project(
    *,
    series_name: str,
    season: int = 1,
    episode: int = 1,
    root_dir: str = ".",
    last_clip_id: int = 0,
) -> Project:
    episode_label = format_episode_label(season, episode)
    ep = Episode(season=season, episode=episode, episode_label=episode_label)
    return Project(
        series_name=series_name,
        root_dir=root_dir,
        last_clip_id=last_clip_id,
        episodes=[ep],
    )
