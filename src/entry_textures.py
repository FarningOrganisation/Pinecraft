"""Gemeinsame Texture-Lookups für Block- und Item-IDs."""

from __future__ import annotations

from blocks import BLOCK_TEXTURES
from items import ITEM_TEXTURES, is_item_id


def get_entry_texture(entry_id: int | None):
    """Liefert die passende Texture für Item- oder Block-IDs."""
    if entry_id is None:
        return None
    if is_item_id(entry_id):
        return ITEM_TEXTURES.get(entry_id)
    return BLOCK_TEXTURES.get(entry_id)
