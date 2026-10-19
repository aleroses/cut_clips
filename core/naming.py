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
    """Nombre base de un clip (sin extensión).

    Serie: {series}_{label}_Line_{id:04d}
    Película (etiqueta vacía): {series}_Line_{id:04d}
    """
    line = f"Line_{clip_id:04d}"
    if episode_label:
        return f"{series_name}_{episode_label}_{line}"
    return f"{series_name}_{line}"


def clip_video_filename(series_name, episode_label, clip_id):
    return f"{clip_basename(series_name, episode_label, clip_id)}.webm"


def clip_audio_filename(series_name, episode_label, clip_id):
    return f"{clip_basename(series_name, episode_label, clip_id)}.mp3"


def tsv_filename(series_name, episode_label, episode_title=None):
    """Nombre por defecto del TSV de Anki.

    Una etiqueta vacía es una película: no se inserta S01E01 ni un guion bajo de más.
    """
    parts = [series_name]
    if episode_label:
        parts.append(episode_label)
    if episode_title:
        parts.append(episode_title)
    parts.append("anki.tsv")
    return "_".join(parts)


def choose_tsv_basename(computed: str, locked: str | None = None) -> str:
    """Reutiliza el TSV ya escrito si un cambio de modo fijó su nombre."""
    return locked or computed


def tsv_lock_after_mode_change(
    current_lock: str | None,
    previous_basename: str,
    previous_exists: bool,
) -> str | None:
    """Conserva el nombre del TSV anterior si ese archivo ya existe."""
    if current_lock:
        return current_lock
    if previous_exists and previous_basename:
        return previous_basename
    return None
