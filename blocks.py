"""Block-Definitionen und Texturen für Pinecraft."""

from pathlib import Path

import arcade

AIR = 0
GRASS = 1
DIRT = 2
STONE = 3
SAND = 4

BLOCKS = {
    GRASS: {"name": "Grass", "texture": "grass.png", "solid": True, "drop_id": DIRT},
    DIRT: {"name": "Dirt", "texture": "dirt.png", "solid": True},
    STONE: {"name": "Stone", "texture": "stone.png", "solid": True, "hardness": 2},
    SAND: {"name": "Sand", "texture": "sand.png", "solid": True},
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

TEXTURE_DIR = Path(__file__).resolve().parent / "assets" / "textures" / "blocks"
BLOCK_TEXTURES = {
    block_id: arcade.load_texture(TEXTURE_DIR / info["texture"])
    for block_id, info in BLOCKS.items()
}
