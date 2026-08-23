"""3x3-Crafting-Rezepte für Pinecraft."""

from blocks import AIR, DIRT, STONE
from items import PICKAXE

CRAFTING_RECIPES = {
    PICKAXE: [
        [
            [STONE, STONE, STONE],
            [AIR, DIRT, AIR],
            [AIR, DIRT, AIR],
        ]
    ]
}
