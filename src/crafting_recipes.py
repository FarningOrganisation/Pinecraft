"""3x3-Crafting-Rezepte für Pinecraft."""

from blocks import OAK, OAK_PLANKS, COBBLESTONE, AIR
from items import (
    CHARCOAL,
    STONE_PICKAXE,
    STONE_SWORD,
    STICK,
    TORCH,
    IRON_PICKAXE,
    IRON_INGOT,
    HAMMER,
)


CRAFTING_RECIPES = {
    # TODO_STUDENT (⭐): Spiel starten und dieses Pickaxe-Rezept nachvollziehen.
    STONE_PICKAXE: {
        "pattern": [
            [COBBLESTONE, COBBLESTONE, COBBLESTONE],
            [AIR, STICK, AIR],
            [AIR, STICK, AIR],
        ],
        "count": 1,
    },
    STONE_SWORD: {
        "pattern": [
            [COBBLESTONE],
            [COBBLESTONE],
            [STICK]
        ],
        "count": 1,
    },
    IRON_PICKAXE: {
        "pattern": [
            [IRON_INGOT, IRON_INGOT, IRON_INGOT],
            [AIR, STICK, AIR],
            [AIR, STICK, AIR],
        ],
        "count": 1,
    },
    HAMMER:
    {
        "pattern": [
            [COBBLESTONE, IRON_INGOT, COBBLESTONE],
            [AIR, STICK, AIR],
            [AIR, STICK, AIR],
        ],
        "count": 1,
    },
    OAK_PLANKS: {
        "pattern": [[OAK]],
        "count": 4,
    },
    STICK: {
        "pattern": [
            [OAK_PLANKS],
            [OAK_PLANKS],
        ],
        "count": 4,
    },
    TORCH: {
        "pattern": [
            [CHARCOAL],
            [STICK],
        ],
        "count": 1,
    },
    # TODO_STUDENT (⭐⭐): Rezept fuer Stone Sword als 3x3-Muster ergaenzen.
    # TODO_STUDENT (⭐⭐⭐): Rezepte fuer Iron/Gold/Diamond Pickaxe ergaenzen.
}
