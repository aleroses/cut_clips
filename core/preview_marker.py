"""Marca visual del clip que se está previsualizando."""


def preview_mark_after_select(preview_id: int | None) -> int | None:
    """Cambiar de fila no mueve la marca."""
    return preview_id


def row_shows_preview_mark(preview_id: int | None, row_id: int) -> bool:
    """La marca se pinta en la fila del clip en prueba, no en la seleccionada."""
    return preview_id is not None and preview_id == row_id


def preview_mark_after_probe(row_id: int) -> int:
    """Probar clip deja la marca en esa fila."""
    return row_id


def preview_mark_after_stop() -> None:
    """Detener la previsualización quita la marca."""
    return None


def preview_mark_after_delete(preview_id: int | None, deleted_id: int) -> int | None:
    """Eliminar el clip en prueba quita la marca. Eliminar otro la deja."""
    if preview_id == deleted_id:
        return None
    return preview_id


def preview_mark_after_edit(
    preview_id: int | None, edited_id: int, *, kept_bounds: bool
) -> int | None:
    """Dividir o fusionar ese clip le quita la marca si perdió los bounds."""
    if preview_id != edited_id:
        return preview_id
    if not kept_bounds:
        return None
    return preview_id
