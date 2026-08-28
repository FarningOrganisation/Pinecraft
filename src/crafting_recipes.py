"""3x3-Crafting-Rezepte für Pinecraft."""

from blocks import AIR, OAK, OAK_PLANKS, COBBLESTONE, COBBLESTONE_BG
from items import (
    CHARCOAL,
    STONE_PICKAXE,
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
        "pattern": [
            [AIR, AIR, AIR],
            [AIR, OAK, AIR],
            [AIR, AIR, AIR],
        ],
        "count": 4,
    },
    STICK: {
        "pattern": [
            [AIR, AIR, AIR],
            [AIR, OAK_PLANKS, AIR],
            [AIR, OAK_PLANKS, AIR],
        ],
        "count": 4,
    },
    TORCH: {
        "pattern": [
            [AIR, AIR, AIR],
            [AIR, CHARCOAL, AIR],
            [AIR, STICK, AIR],
        ],
        "count": 1,
    },

    COBBLESTONE_BG: {
        "pattern": [[COBBLESTONE]],
        "count": 1
    },

    # TODO_STUDENT (⭐⭐): Rezept fuer Stone Sword als 3x3-Muster ergaenzen.
    # TODO_STUDENT (⭐⭐⭐): Rezepte fuer Iron/Gold/Diamond Pickaxe ergaenzen.
}
