"""Item-Definitionen und Texturen für Pinecraft."""

from pathlib import Path

import arcade

ITEM_ID_START = 1024


PICKAXE = ITEM_ID_START
CHARCOAL = ITEM_ID_START + 1
IRON_INGOT = ITEM_ID_START + 2
GOLD_INGOT = ITEM_ID_START + 3
DIAMOND = ITEM_ID_START + 4
STICK = ITEM_ID_START + 5
TORCH = ITEM_ID_START + 6
STONE_SWORD = ITEM_ID_START + 7

ITEMS = {
    PICKAXE: {
        "item_id": PICKAXE,
        "name": "Stone Pickaxe",
        "texture": "stone_pickaxe.png",
        "item_type": "tool",  # consumable, tool, material
        "max_stack": 1,
        "mining_speed": 2,
    },
    STONE_SWORD: {
        "item_id": STONE_SWORD,
        "name": "Stone Sword",
        "texture": "stone_sword.png",
        "item_type": "tool",
        "max_stack": 1,
        "attack_damage": 2,
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
    STICK: {
        "item_id": STICK,
        "name": "Stick",
        "texture": "stick.png",
        "item_type": "material",
        "max_stack": 64,
    },
    TORCH: {
        "item_id": TORCH,
        "name": "Torch",
        "texture": "torch_on.png",
        "item_type": "light",
        "max_stack": 64,
        "texture_dir": "blocks",
    },
}

TEXTURE_ROOT = Path(__file__).resolve().parent / "assets" / "textures"


def _item_texture_path(item_definition: dict) -> Path:
    texture_dir = item_definition.get("texture_dir", "items")
    return TEXTURE_ROOT / texture_dir / item_definition["texture"]


ITEM_TEXTURES = {
    item_id: arcade.load_texture(_item_texture_path(item))
    for item_id, item in ITEMS.items()
}


def is_item_id(entry_id) -> bool:
    """Prüft, ob eine ID zu einem Item gehört."""
    return isinstance(entry_id, int) and entry_id >= ITEM_ID_START
