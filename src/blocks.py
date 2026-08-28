"""Block-Definitionen und Texturen für Pinecraft."""

import math
from pathlib import Path

import arcade
from paths import textures_dir
from resource_manager import resource_manager

AIR = 0
GRASS = 1
DIRT = 2
STONE = 3
SAND = 4
BEDROCK = 5
OAK = 6
LEAVES = 7
COAL_ORE = 8
IRON_ORE = 9
GOLD_ORE = 10
DIAMOND_ORE = 11
OAK_PLANKS = 12
COBBLESTONE = 13
SAND = 14
OBSIDIAN = 15

from items import CHARCOAL, DIAMOND, GOLD_INGOT, IRON_INGOT

BLOCKS = {
    GRASS: {"name": "Grass", "texture": "grass.png", "solid": True, "drop_id": DIRT, "falling": False},
    DIRT: {"name": "Dirt", "texture": "dirt.png", "solid": True, "falling": False},
    STONE: {"name": "Stone", "texture": "stone.png", "solid": True, "hardness": 2, "drop_id": COBBLESTONE, "falling": False},
    SAND: {"name": "Sand", "texture": "sand.png", "solid": True, "falling": True},
    BEDROCK: {"name": "Bedrock", "texture": "bedrock.png", "solid": True, "hardness": float("inf"), "falling": False},
    OAK: {"name": "Oak", "texture": "oak.png", "solid": False, "skylight_surface": False, "falling": False},
    LEAVES: {
        "name": "Leaves",
        "texture": "leaves.png",
        "solid": False,
        "light_opacity": 0.18,
        "skylight_surface": False,
        "falling": False,
    },
    COAL_ORE: {"name": "Coal Ore", "texture": "coal_ore.png", "solid": True, "hardness": 2.2, "drop_id": CHARCOAL, "falling": False},
    IRON_ORE: {"name": "Iron Ore", "texture": "iron_ore.png", "solid": True, "hardness": 2.4, "drop_id": IRON_INGOT, "falling": False},
    GOLD_ORE: {"name": "Gold Ore", "texture": "gold_ore.png", "solid": True, "hardness": 2.6, "drop_id": GOLD_INGOT, "falling": False},
    DIAMOND_ORE: {"name": "Diamond Ore", "texture": "diamond_ore.png", "solid": True, "hardness": 3.0, "drop_id": DIAMOND, "falling": False},
    OAK_PLANKS: {"name": "Oak Planks", "texture": "planks_oak.png", "solid": True, "falling": False},
    COBBLESTONE: {"name": "Cobblestone", "texture": "cobblestone.png", "solid": True, "hardness": 2.0, "falling": False},
    OBSIDIAN: {"name": "Obsidian", "texture": "obsidian.png", "solid": True, "hardness": 10}
}


def get_block_drop_id(block_id: int) -> int | None:
    """Liefert die Drop-ID eines Blocks oder None für unbekannte IDs."""
    block_definition = BLOCKS.get(block_id)
    if block_definition is None:
        return None
    return block_definition.get("drop_id", block_id)


def get_block_hardness(block_id: int) -> float:
    """Liefert die Hardness eines Blocks (Default: 1.0)."""
    block_definition = BLOCKS.get(block_id)
    if block_definition is None:
        return 1.0
    hardness = block_definition.get("hardness", 1.0)
    try:
        hardness_value = float(hardness)
    except (TypeError, ValueError):
        return 1.0
    return max(0.01, hardness_value)


def is_block_breakable(block_id: int) -> bool:
    """True, wenn ein Block abbaubar ist (endliche Hardness)."""
    return math.isfinite(get_block_hardness(block_id))


def is_block_solid(block_id: int) -> bool:
    """True, wenn ein Block kollidierbar ist."""
    block_definition = BLOCKS.get(block_id)
    if block_definition is None:
        return False
    return bool(block_definition.get("solid", True))


def is_block_water_passable(block_id: int) -> bool:
    """True, wenn Wasser diese Tile als offenen Bereich behandeln darf."""
    if block_id == AIR:
        return True
    block_definition = BLOCKS.get(block_id)
    if block_definition is None:
        return False
    return not bool(block_definition.get("solid", True))


def is_block_falling(block_id: int) -> bool:
    """True, wenn ein Block aufgrund der Schwerkraft fällt."""
    block_definition = BLOCKS.get(block_id)
    if block_definition is None:
        return False
    return bool(block_definition.get("falling", False))


def get_block_light_opacity(block_id: int) -> float:
    """Liefert Licht-Undurchlässigkeit zwischen 0.0 (durchlässig) und 1.0 (opak)."""
    if block_id == AIR:
        return 0.0

    block_definition = BLOCKS.get(block_id)
    if block_definition is None:
        return 1.0

    try:
        opacity = float(block_definition.get("light_opacity", 1.0))
    except (TypeError, ValueError):
        return 1.0
    return max(0.0, min(1.0, opacity))


def is_block_skylight_surface(block_id: int) -> bool:
    """True, wenn der Block als natürliche Oberfläche für Skylight zählen soll."""
    if block_id == AIR:
        return False

    block_definition = BLOCKS.get(block_id)
    if block_definition is None:
        return True
    return bool(block_definition.get("skylight_surface", True))

TEXTURE_DIR = textures_dir("blocks")
BLOCK_TEXTURES = {
    block_id: resource_manager.load_texture_in_textures(Path("blocks") / info["texture"])
    for block_id, info in BLOCKS.items()
}
