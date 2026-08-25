"""3x3-Crafting-Rezepte für Pinecraft."""

from blocks import AIR, DIRT, OAK, OAK_PLANKS, STONE, COBBLESTONE
from items import (
    CHARCOAL, 
    STONE_PICKAXE, 
    STICK, 
    TORCH,
    IRON_PICKAXE,
    IRON_INGOT
)


def _single_cell_variants(item_id: int) -> list[list[list[int]]]:
    """Erzeugt alle 3x3-Varianten mit genau einem Item."""
    variants: list[list[list[int]]] = []
    for row in range(3):
        for col in range(3):
            grid = [[AIR, AIR, AIR], [AIR, AIR, AIR], [AIR, AIR, AIR]]
            grid[row][col] = item_id
            variants.append(grid)
    return variants


def _vertical_pair_variants(top_item: int, bottom_item: int) -> list[list[list[int]]]:
    """Erzeugt alle 3x3-Varianten für zwei vertikal angeordnete Items."""
    variants: list[list[list[int]]] = []
    for row in range(2):
        for col in range(3):
            grid = [[AIR, AIR, AIR], [AIR, AIR, AIR], [AIR, AIR, AIR]]
            grid[row][col] = top_item
            grid[row + 1][col] = bottom_item
            variants.append(grid)
    return variants

CRAFTING_RECIPES = {
    # TODO_STUDENT (⭐): Spiel starten und dieses Pickaxe-Rezept nachvollziehen.
    STONE_PICKAXE: [
        {
            "pattern": [
                [COBBLESTONE, COBBLESTONE, COBBLESTONE],
                [AIR, STICK, AIR],
                [AIR, STICK, AIR],
            ],
            "count": 1,
        }
    ],
    IRON_PICKAXE: [
        {
            "pattern": [
                [IRON_INGOT, IRON_INGOT, IRON_INGOT],
                [AIR, STICK, AIR],
                [AIR, STICK, AIR],
                        ],
            "count": 1,
        }
    ],
    OAK_PLANKS: [
        {"pattern": pattern, "count": 4}
        for pattern in _single_cell_variants(OAK)
    ],
    STICK: [
        {"pattern": pattern, "count": 4}
        for pattern in _vertical_pair_variants(OAK_PLANKS, OAK_PLANKS)
    ],
    TORCH: [
        {"pattern": pattern, "count": 1}
        for pattern in _vertical_pair_variants(CHARCOAL, STICK)
    ],
    # TODO_STUDENT (⭐⭐): Rezept fuer Stone Sword als 3x3-Muster ergaenzen.
    # TODO_STUDENT (⭐⭐⭐): Rezepte fuer Iron/Gold/Diamond Pickaxe ergaenzen.
}
