"""Item-Definitionen und Texturen für Pinecraft."""

from pathlib import Path

import arcade

ITEM_ID_START = 1024


PICKAXE = ITEM_ID_START

ITEMS = {
    PICKAXE: {
        "item_id": PICKAXE,
        "name": "Stone Pickaxe",
        "texture": "stone_pickaxe.png",
        "item_type": "tool",  # consumable, tool, material
        "max_stack": 1,
        "mining_speed": 2,
    },
}

TEXTURE_DIR = Path(__file__).resolve().parent / "assets" / "textures" / "items"
ITEM_TEXTURES = {
    item_id: arcade.load_texture(TEXTURE_DIR / item["texture"])
    for item_id, item in ITEMS.items()
}


def is_item_id(entry_id) -> bool:
    """Prüft, ob eine ID zu einem Item gehört."""
    return isinstance(entry_id, int) and entry_id >= ITEM_ID_START
