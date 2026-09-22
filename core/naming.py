"""Generación centralizada de nombres de episodio y archivos de clip."""


def format_episode_label(season, episode, style="legacy"):
    """Genera etiqueta de episodio a partir de temporada y número.

    style='legacy' produce el formato histórico del CLI: S01-Ep01
    style='compact' produce S01E01
    """
    if style == "compact":
        return f"S{season:02d}E{episode:02d}"
    return f"S{season:02d}-Ep{episode:02d}"


def clip_basename(series_name, episode_label, clip_id):
    """Nombre base de un clip (sin extensión): {series}_{label}_Line_{id:04d}"""
    return f"{series_name}_{episode_label}_Line_{clip_id:04d}"


def clip_video_filename(series_name, episode_label, clip_id):
    return f"{clip_basename(series_name, episode_label, clip_id)}.webm"


def clip_audio_filename(series_name, episode_label, clip_id):
    return f"{clip_basename(series_name, episode_label, clip_id)}.mp3"


def tsv_filename(series_name, episode_label, episode_title=None):
    """Nombre por defecto del TSV de Anki."""
    if episode_title:
        return f"{series_name}_{episode_label}_{episode_title}_anki.tsv"
    return f"{series_name}_{episode_label}_anki.tsv"
