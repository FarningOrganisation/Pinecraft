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
COBBLESTONE_BG = 16

BACKGROUND_BLOCK_ID_OFFSET = 200
SOLID_BLOCK_ID_OFFSET = 400

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
    OBSIDIAN: {"name": "Obsidian", "texture": "obsidian.png", "solid": True, "hardness": 10},
    COBBLESTONE_BG: {"name": "Cobblestone Background", "texture": "background/cobblestone.png", "solid": False}
}

EXCLUDED_BACKGROUND_CONVERSION_BLOCKS = {AIR, BEDROCK}

# Direkte Spezialzuordnungen behalten bestehende IDs stabil.
_EXPLICIT_NORMAL_TO_BACKGROUND = {
    COBBLESTONE: COBBLESTONE_BG,
}

NORMAL_TO_BACKGROUND_BLOCK: dict[int, int] = {}
BACKGROUND_TO_NORMAL_BLOCK: dict[int, int] = {}


def _unique_block_id(preferred_id: int) -> int:
    """Findet eine freie Block-ID auf Basis eines Offset-Bereichs."""
    candidate = preferred_id
    while candidate in BLOCKS:
        candidate += 1
    return candidate


def _build_background_conversion_tables() -> None:
    """Erzeugt 1:1-Konvertierung für normale und Hintergrundblöcke."""
    block_texture_dir = textures_dir("blocks")

    for normal_id, background_id in _EXPLICIT_NORMAL_TO_BACKGROUND.items():
        if normal_id in BLOCKS and background_id in BLOCKS:
            NORMAL_TO_BACKGROUND_BLOCK[normal_id] = background_id
            BACKGROUND_TO_NORMAL_BLOCK[background_id] = normal_id

    # list(...) damit neu angelegte Varianten den Loop nicht beeinflussen.
    for block_id, info in list(BLOCKS.items()):
        if block_id == AIR:
            continue

        if block_id in NORMAL_TO_BACKGROUND_BLOCK or block_id in BACKGROUND_TO_NORMAL_BLOCK:
            continue

        name = str(info.get("name", f"Block {block_id}"))
        texture = str(info.get("texture", ""))
        solid = bool(info.get("solid", True))

        if solid:
            if block_id in EXCLUDED_BACKGROUND_CONVERSION_BLOCKS:
                continue

            bg_texture = texture if texture.startswith("background/") else f"background/{texture}"
            if not (block_texture_dir / bg_texture).exists():
                continue

            bg_id = _unique_block_id(BACKGROUND_BLOCK_ID_OFFSET + block_id)
            bg_info = dict(info)
            bg_info["name"] = f"{name} Background"
            bg_info["texture"] = bg_texture
            bg_info["solid"] = False
            bg_info["falling"] = False
            BLOCKS[bg_id] = bg_info

            NORMAL_TO_BACKGROUND_BLOCK[block_id] = bg_id
            BACKGROUND_TO_NORMAL_BLOCK[bg_id] = block_id
            continue

        # Nicht-solide Originale (z. B. Oak/Leaves) gelten als "Hintergrund".
        # Sie nutzen daher die Hintergrundtextur; die erzeugte solide Variante
        # bleibt auf der normalen (helleren) Textur.
        normal_texture = texture.removeprefix("background/")
        background_texture = f"background/{normal_texture}"
        if (block_texture_dir / background_texture).exists():
            info["texture"] = background_texture

        solid_id = _unique_block_id(SOLID_BLOCK_ID_OFFSET + block_id)
        solid_info = dict(info)
        solid_info["name"] = f"{name} Solid"
        solid_info["texture"] = normal_texture
        solid_info["solid"] = True
        solid_info["falling"] = False
        BLOCKS[solid_id] = solid_info

        BACKGROUND_TO_NORMAL_BLOCK[block_id] = solid_id
        NORMAL_TO_BACKGROUND_BLOCK[solid_id] = block_id


def get_background_block_id(block_id: int) -> int | None:
    """Liefert die Hintergrundvariante eines normalen Blocks."""
    return NORMAL_TO_BACKGROUND_BLOCK.get(block_id)


def get_foreground_block_id(block_id: int) -> int | None:
    """Liefert die normale/solide Variante eines Hintergrundblocks."""
    return BACKGROUND_TO_NORMAL_BLOCK.get(block_id)


def get_convertible_partner_block_id(block_id: int) -> int | None:
    """Liefert das jeweilige Gegenstück für die 1:1-Konvertierung."""
    partner = NORMAL_TO_BACKGROUND_BLOCK.get(block_id)
    if partner is not None:
        return partner
    return BACKGROUND_TO_NORMAL_BLOCK.get(block_id)


def is_background_block(block_id: int) -> bool:
    """True, wenn die ID als Hintergrundvariante behandelt wird."""
    return block_id in BACKGROUND_TO_NORMAL_BLOCK


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
_build_background_conversion_tables()
BLOCK_TEXTURES = {
    block_id: resource_manager.load_texture_in_textures(Path("blocks") / info["texture"])
    for block_id, info in BLOCKS.items()
}
