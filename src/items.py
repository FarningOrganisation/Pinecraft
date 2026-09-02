"""Item-Definitionen und Texturen für Pinecraft."""

from pathlib import Path

import arcade
from ids import (
    DIRT,
    GRASS,
    CHARCOAL,
    DIAMOND,
    EGG,
    FEATHER,
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
    FEATHER: {
        "item_id": FEATHER,
        "name": "Feather",
        "texture": "feather.png",
        "item_type": "material",
        "max_stack": 64,
    },
    EGG: {
        "item_id": EGG,
        "name": "Egg",
        "texture": "egg.png",
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
        # Student-Hinweis: place_as="item" + placement_rules machen ein Item platzierbar.
        "place_as": "item",
        "placement_rules": {
            "allowed_support_blocks": [GRASS, DIRT],
            "requires_surface_exposure_for_growth": True,
        },
    },
    
}


def _warn_item_hint(item_id: object, message: str) -> None:
    print(f"[items][hint] item={item_id}: {message}")


def _validate_item_definitions() -> None:
    """Gibt fruehe Hinweise bei fehlerhaften Itemdefinitionen aus."""
    valid_types = {"tool", "consumable", "material", "light", "nature"}
    valid_place_as = {"item", "block"}

    for item_id, definition in ITEMS.items():
        if not isinstance(item_id, int):
            _warn_item_hint(item_id, "ID sollte ein int sein.")

        if not isinstance(definition, dict):
            _warn_item_hint(item_id, "Definition sollte ein dict sein.")
            continue

        if definition.get("item_id") != item_id:
            _warn_item_hint(item_id, "'item_id' sollte mit dem Dictionary-Key uebereinstimmen.")

        if not definition.get("name"):
            _warn_item_hint(item_id, "'name' fehlt oder ist leer.")

        texture_name = definition.get("texture")
        if not isinstance(texture_name, str) or not texture_name.strip():
            _warn_item_hint(item_id, "'texture' fehlt oder ist ungueltig.")

        item_type = definition.get("item_type")
        if item_type not in valid_types:
            _warn_item_hint(item_id, f"'item_type' sollte einer von {sorted(valid_types)} sein.")

        try:
            max_stack = int(definition.get("max_stack", 0))
            if max_stack <= 0:
                _warn_item_hint(item_id, "'max_stack' sollte > 0 sein.")
        except (TypeError, ValueError):
            _warn_item_hint(item_id, "'max_stack' muss numerisch sein.")

        place_as = definition.get("place_as")
        if place_as is not None and place_as not in valid_place_as:
            _warn_item_hint(item_id, "'place_as' sollte 'item' oder 'block' sein.")

        rules = definition.get("placement_rules")
        if rules is not None and not isinstance(rules, dict):
            _warn_item_hint(item_id, "'placement_rules' sollte ein dict sein.")

        if isinstance(rules, dict):
            support_blocks = rules.get("allowed_support_blocks")
            if support_blocks is not None and not isinstance(support_blocks, (list, tuple, set)):
                _warn_item_hint(item_id, "'allowed_support_blocks' sollte list/tuple/set sein.")

TEXTURE_ROOT = textures_dir()
_validate_item_definitions()


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
