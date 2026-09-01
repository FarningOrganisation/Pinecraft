"""Item-Definitionen und Texturen für Pinecraft."""

from pathlib import Path

import arcade
from ids import (
    DIRT,
    GRASS,
    CHARCOAL,
    DIAMOND,
    GOLD_INGOT,
    HAMMER,
    IRON_INGOT,
    IRON_PICKAXE,
    ITEM_ID_START,
    SAPLING_OAK,
    STICK,
    STONE_PICKAXE,
    STONE_SWORD,
    TORCH,
)
from paths import textures_dir
from resource_manager import resource_manager
ITEMS = {
    STONE_PICKAXE: {
        "item_id": STONE_PICKAXE,
        "name": "Stone Pickaxe",
        "texture": "stone_pickaxe.png",
        "item_type": "tool",  # consumable, tool, material
        "max_stack": 1,
        "mining_speed": 1000,
    },
    IRON_PICKAXE: {
        "item_id": IRON_PICKAXE,
        "name": "Iron Pickaxe",
        "texture": "iron_pickaxe.png",
        "item_type": "tool",
        "max_stack": 1,
        "mining_speed": 3
    },
    HAMMER: {
                "item_id": HAMMER,
                "name": "HAMMER",
                "texture": "hammer.png",
                "item_type": "tool",
                "max_stack": 1,
                "attack_damage": 20,
     },
    STONE_SWORD: {
        "item_id": STONE_SWORD,
        "name": "Stone Sword",
        "texture": "stone_sword.png",
        "item_type": "tool",
        "max_stack": 1,
        "attack_damage": 2,
    },
    # TODO_STUDENT (⭐⭐⭐): Weitere Tools wie Iron/Gold/Diamond Pickaxe hier anlegen.
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
        "place_as": "item",
    },
    SAPLING_OAK: {
        "item_id": SAPLING_OAK,
        "name": "Oak Sapling",
        "texture": "sapling_oak.png",
        "item_type": "nature",
        "max_stack": 64,
        "texture_dir": "blocks",
        "place_as": "item",
        "placement_rules": {
            "allowed_support_blocks": [GRASS, DIRT],
            "requires_surface_exposure_for_growth": True,
        },
    },
}

TEXTURE_ROOT = textures_dir()


def _item_texture_path(item_definition: dict) -> Path:
    texture_dir = item_definition.get("texture_dir", "items")
    return TEXTURE_ROOT / texture_dir / item_definition["texture"]


ITEM_TEXTURES = {
    item_id: resource_manager.load_texture(_item_texture_path(item))
    for item_id, item in ITEMS.items()
}


def is_item_id(entry_id) -> bool:
    """Prüft, ob eine ID zu einem Item gehört."""
    return isinstance(entry_id, int) and entry_id >= ITEM_ID_START
