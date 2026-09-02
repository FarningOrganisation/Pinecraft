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


def _warn_recipe_hint(result_item_id: object, message: str) -> None:
    print(f"[crafting][hint] result={result_item_id}: {message}")


def _validate_crafting_recipes() -> None:
    """Gibt fruehe Hinweise bei fehlerhaften Rezept-Definitionen aus."""
    from blocks import BLOCKS
    from items import ITEMS

    known_entry_ids = set(BLOCKS.keys()) | set(ITEMS.keys()) | {AIR}

    for result_item_id, recipe in CRAFTING_RECIPES.items():
        if result_item_id not in known_entry_ids:
            _warn_recipe_hint(result_item_id, "Result-ID ist weder Block noch Item.")

        if not isinstance(recipe, dict):
            _warn_recipe_hint(result_item_id, "Rezept sollte ein dict mit 'pattern' und optional 'count' sein.")
            continue

        pattern = recipe.get("pattern")
        if not isinstance(pattern, list) or not pattern:
            _warn_recipe_hint(result_item_id, "'pattern' fehlt oder ist ungueltig.")
            continue

        if len(pattern) > 3:
            _warn_recipe_hint(result_item_id, "Pattern darf hoechstens 3 Zeilen haben.")

        for row_index, row in enumerate(pattern):
            if not isinstance(row, list):
                _warn_recipe_hint(result_item_id, f"Zeile {row_index} ist keine Liste.")
                continue
            if len(row) > 3:
                _warn_recipe_hint(result_item_id, f"Zeile {row_index} hat mehr als 3 Spalten.")

            for col_index, entry_id in enumerate(row):
                if entry_id not in known_entry_ids:
                    _warn_recipe_hint(
                        result_item_id,
                        f"Pattern-Zelle ({row_index},{col_index}) nutzt unbekannte ID {entry_id}.",
                    )

        try:
            count = int(recipe.get("count", 1))
            if count <= 0:
                _warn_recipe_hint(result_item_id, "'count' sollte > 0 sein.")
        except (TypeError, ValueError):
            _warn_recipe_hint(result_item_id, "'count' muss numerisch sein.")


_validate_crafting_recipes()
