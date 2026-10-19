"""Qué línea queda seleccionada después de eliminar un clip."""


def next_id_after_removal(ordered_ids: list[int], removed_id: int) -> int | None:
    """Id que pasa a ser el actual tras quitar removed_id.

    ordered_ids es el orden visible antes de borrar. Si hay una línea
    siguiente, esa; si se borró la última, la anterior; si no queda
    ninguna, None.
    """
    try:
        index = ordered_ids.index(removed_id)
    except ValueError:
        remaining = [item_id for item_id in ordered_ids if item_id != removed_id]
        return remaining[0] if remaining else None

    remaining = [item_id for item_id in ordered_ids if item_id != removed_id]
    if not remaining:
        return None
    if index < len(remaining):
        return remaining[index]
    return remaining[-1]
