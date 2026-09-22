"""Modelo de datos del proyecto Anki Video Tool."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


SCHEMA_VERSION = 1


class ClipStatus(str, Enum):
    PENDING = "pending"
    MODIFIED = "modified"
    PREVIEW = "preview"
    GENERATED = "generated"
    OUTDATED = "outdated"
    ERROR = "error"


@dataclass
class SubtitleCue:
    """Un bloque de subtítulo dentro del episodio."""

    index: int
    start: float
    end: float
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "start": self.start,
            "end": self.end,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SubtitleCue:
        return cls(
            index=int(data["index"]),
            start=float(data["start"]),
            end=float(data["end"]),
            text=str(data["text"]),
        )


@dataclass
class TranslationConfig:
    """Configuración de traducción (sin almacenar API keys)."""

    provider: str = "none"  # none, deepl, openai, ...
    target_lang: str = "ES"
    cache_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "target_lang": self.target_lang,
            "cache_path": self.cache_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TranslationConfig:
        return cls(
            provider=str(data.get("provider", "none")),
            target_lang=str(data.get("target_lang", "ES")),
            cache_path=str(data.get("cache_path", "")),
        )


@dataclass
class Clip:
    """Clip de estudio asociado a uno o más subtítulos."""

    id: int
    internal_index: int
    subtitle_indices: list[int] = field(default_factory=list)
    text: str = ""
    translation: str = ""
    start: float = 0.0
    end: float = 0.0
    padding_start: float = 0.0
    padding_end: float = 0.0
    status: ClipStatus = ClipStatus.PENDING
    video_path: str = ""
    audio_path: str = ""
    generation_fingerprint: dict[str, Any] = field(default_factory=dict)
    error_message: str = ""

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    @property
    def padded_start(self) -> float:
        return max(0.0, self.start - self.padding_start)

    @property
    def padded_end(self) -> float:
        return self.end + self.padding_end

    def compute_fingerprint(
        self,
        *,
        video_path: str,
        audio_track: int = 0,
        video_track: int = 0,
        width: int = 640,
        height: int = 480,
        crf: int = 32,
    ) -> dict[str, Any]:
        """Fingerprint de la configuración usada para generar el clip."""
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "padding_start": round(self.padding_start, 3),
            "padding_end": round(self.padding_end, 3),
            "text": self.text,
            "video_path": video_path,
            "audio_track": audio_track,
            "video_track": video_track,
            "width": width,
            "height": height,
            "crf": crf,
        }

    def is_outdated(self, current: dict[str, Any]) -> bool:
        """True si la config actual difiere de la usada en la última generación."""
        if self.status != ClipStatus.GENERATED:
            return False
        return self.generation_fingerprint != current

    def mark_generated(self, fingerprint: dict[str, Any], video_path: str, audio_path: str):
        self.generation_fingerprint = dict(fingerprint)
        self.video_path = video_path
        self.audio_path = audio_path
        self.status = ClipStatus.GENERATED
        self.error_message = ""

    def mark_modified(self):
        if self.status == ClipStatus.GENERATED:
            self.status = ClipStatus.OUTDATED
        elif self.status not in (ClipStatus.ERROR, ClipStatus.PREVIEW):
            self.status = ClipStatus.MODIFIED

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "internal_index": self.internal_index,
            "subtitle_indices": list(self.subtitle_indices),
            "text": self.text,
            "translation": self.translation,
            "start": self.start,
            "end": self.end,
            "padding_start": self.padding_start,
            "padding_end": self.padding_end,
            "status": self.status.value,
            "video_path": self.video_path,
            "audio_path": self.audio_path,
            "generation_fingerprint": dict(self.generation_fingerprint),
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Clip:
        return cls(
            id=int(data["id"]),
            internal_index=int(data.get("internal_index", data["id"])),
            subtitle_indices=[int(i) for i in data.get("subtitle_indices", [])],
            text=str(data.get("text", "")),
            translation=str(data.get("translation", "")),
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            padding_start=float(data.get("padding_start", 0.0)),
            padding_end=float(data.get("padding_end", 0.0)),
            status=ClipStatus(data.get("status", ClipStatus.PENDING.value)),
            video_path=str(data.get("video_path", "")),
            audio_path=str(data.get("audio_path", "")),
            generation_fingerprint=dict(data.get("generation_fingerprint", {})),
            error_message=str(data.get("error_message", "")),
        )


@dataclass
class Episode:
    """Estado de un episodio en edición."""

    video_path: str = ""
    season: int = 1
    episode: int = 1
    episode_label: str = ""
    episode_title: str = ""
    subtitle_path: str = ""
    subtitle_track_index: int | None = None
    subtitle_language: str = "en"
    audio_track: int = 0
    video_track: int = 0
    padding_start: float = 0.0
    padding_end: float = 0.0
    media_info: dict[str, Any] = field(default_factory=dict)
    subtitles: list[SubtitleCue] = field(default_factory=list)
    clips: list[Clip] = field(default_factory=list)
    translation: TranslationConfig = field(default_factory=TranslationConfig)
    output_dir: str = "output_files"

    def __post_init__(self):
        if not self.episode_label:
            from core.naming import format_episode_label
            self.episode_label = format_episode_label(self.season, self.episode)

    def next_clip_id(self, project_last_id: int) -> int:
        if self.clips:
            return max(c.id for c in self.clips) + 1
        return project_last_id + 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_path": self.video_path,
            "season": self.season,
            "episode": self.episode,
            "episode_label": self.episode_label,
            "episode_title": self.episode_title,
            "subtitle_path": self.subtitle_path,
            "subtitle_track_index": self.subtitle_track_index,
            "subtitle_language": self.subtitle_language,
            "audio_track": self.audio_track,
            "video_track": self.video_track,
            "padding_start": self.padding_start,
            "padding_end": self.padding_end,
            "media_info": dict(self.media_info),
            "subtitles": [s.to_dict() for s in self.subtitles],
            "clips": [c.to_dict() for c in self.clips],
            "translation": self.translation.to_dict(),
            "output_dir": self.output_dir,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Episode:
        ep = cls(
            video_path=str(data.get("video_path", "")),
            season=int(data.get("season", 1)),
            episode=int(data.get("episode", 1)),
            episode_label=str(data.get("episode_label", "")),
            episode_title=str(data.get("episode_title", "")),
            subtitle_path=str(data.get("subtitle_path", "")),
            subtitle_track_index=data.get("subtitle_track_index"),
            subtitle_language=str(data.get("subtitle_language", "en")),
            audio_track=int(data.get("audio_track", 0)),
            video_track=int(data.get("video_track", 0)),
            padding_start=float(data.get("padding_start", 0.0)),
            padding_end=float(data.get("padding_end", 0.0)),
            media_info=dict(data.get("media_info", {})),
            subtitles=[SubtitleCue.from_dict(s) for s in data.get("subtitles", [])],
            clips=[Clip.from_dict(c) for c in data.get("clips", [])],
            translation=TranslationConfig.from_dict(data.get("translation", {})),
            output_dir=str(data.get("output_dir", "output_files")),
        )
        return ep


@dataclass
class Project:
    """Proyecto de una serie; puede contener uno o más episodios."""

    series_name: str = ""
    root_dir: str = "."
    last_clip_id: int = 0
    episodes: list[Episode] = field(default_factory=list)
    modified: bool = False

    @property
    def next_clip_id(self) -> int:
        return self.last_clip_id + 1

    def bump_last_clip_id(self, clip_id: int):
        if clip_id > self.last_clip_id:
            self.last_clip_id = clip_id

    def current_episode(self) -> Episode | None:
        return self.episodes[-1] if self.episodes else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "series_name": self.series_name,
            "root_dir": self.root_dir,
            "last_clip_id": self.last_clip_id,
            "episodes": [e.to_dict() for e in self.episodes],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Project:
        version = int(data.get("schema_version", 1))
        if version != SCHEMA_VERSION:
            raise ValueError(
                f"Versión de esquema no soportada: {version} (esperada {SCHEMA_VERSION})"
            )
        return cls(
            series_name=str(data.get("series_name", "")),
            root_dir=str(data.get("root_dir", ".")),
            last_clip_id=int(data.get("last_clip_id", 0)),
            episodes=[Episode.from_dict(e) for e in data.get("episodes", [])],
        )
