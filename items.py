"""Item-Definitionen und Texturen für Pinecraft."""

from pathlib import Path

import arcade

ITEM_ID_START = 1024


PICKAXE = ITEM_ID_START
CHARCOAL = ITEM_ID_START + 1
IRON_INGOT = ITEM_ID_START + 2
GOLD_INGOT = ITEM_ID_START + 3
DIAMOND = ITEM_ID_START + 4

ITEMS = {
    PICKAXE: {
        "item_id": PICKAXE,
        "name": "Stone Pickaxe",
        "texture": "stone_pickaxe.png",
        "item_type": "tool",  # consumable, tool, material
        "max_stack": 1,
        "mining_speed": 2,
    },
    CHARCOAL: {
        "item_id": CHARCOAL,
        "name": "Charcoal",
        "texture": "charcoal.png",
        "item_type": "material",
        "max_stack": 64,
    },
    IRON_INGOT: {
        "item_id": IRON_INGOT,
        "name": "Iron Ingot",
        "texture": "iron_ingot.png",
        "item_type": "material",
        "max_stack": 64,
    },
    GOLD_INGOT: {
        "item_id": GOLD_INGOT,
        "name": "Gold Ingot",
        "texture": "gold_ingot.png",
        "item_type": "material",
        "max_stack": 64,
    },
    DIAMOND: {
        "item_id": DIAMOND,
        "name": "Diamond",
        "texture": "diamond.png",
        "item_type": "material",
        "max_stack": 64,
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
