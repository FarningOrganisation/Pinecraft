"""Block-Definitionen und Texturen für Pinecraft."""

import math
from pathlib import Path

import arcade

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

from items import CHARCOAL, DIAMOND, GOLD_INGOT, IRON_INGOT

BLOCKS = {
    GRASS: {"name": "Grass", "texture": "grass.png", "solid": True, "drop_id": DIRT},
    DIRT: {"name": "Dirt", "texture": "dirt.png", "solid": True},
    STONE: {"name": "Stone", "texture": "stone.png", "solid": True, "hardness": 2},
    SAND: {"name": "Sand", "texture": "sand.png", "solid": True},
    BEDROCK: {"name": "Bedrock", "texture": "bedrock.png", "solid": True, "hardness": float("inf")},
    OAK: {"name": "Oak", "texture": "oak.png", "solid": True},
    LEAVES: {"name": "Leaves", "texture": "leaves.png", "solid": False},
    COAL_ORE: {"name": "Coal Ore", "texture": "coal_ore.png", "solid": True, "hardness": 2.2, "drop_id": CHARCOAL},
    IRON_ORE: {"name": "Iron Ore", "texture": "iron_ore.png", "solid": True, "hardness": 2.4, "drop_id": IRON_INGOT},
    GOLD_ORE: {"name": "Gold Ore", "texture": "gold_ore.png", "solid": True, "hardness": 2.6, "drop_id": GOLD_INGOT},
    DIAMOND_ORE: {"name": "Diamond Ore", "texture": "diamond_ore.png", "solid": True, "hardness": 3.0, "drop_id": DIAMOND},
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

TEXTURE_DIR = Path(__file__).resolve().parent / "assets" / "textures" / "blocks"
BLOCK_TEXTURES = {
    block_id: arcade.load_texture(TEXTURE_DIR / info["texture"])
    for block_id, info in BLOCKS.items()
}
