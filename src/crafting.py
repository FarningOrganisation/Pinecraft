"""Hilfsfunktionen für die Crafting-Rezept-Erkennung."""

from blocks import AIR


def _non_air_cells(grid):
    """Gibt alle nicht-leeren Zellen als {(row, col): item_id} zurück."""
    return {
        (row_index, col_index): value
        for row_index, row in enumerate(grid)
        for col_index, value in enumerate(row)
        if value != AIR
    }


def matches_pattern(grid, pattern):
    """Prüft, ob ein Rezept-Muster an beliebiger Position im 3x3-Grid passt."""
    if len(grid) != 3 or any(len(row) != 3 for row in grid):
        return False, None
    if len(pattern) != 3 or any(len(row) != 3 for row in pattern):
        return False, None

    grid_cells = _non_air_cells(grid)
    pattern_cells = _non_air_cells(pattern)

    if not pattern_cells:
        return (not grid_cells), (0, 0)
    if len(grid_cells) != len(pattern_cells):
        return False, None

    for row_offset in range(3):
        for col_offset in range(3):
            translated_pattern = {}
            valid_translation = True

            for (row, col), value in pattern_cells.items():
                target_row = row + row_offset
                target_col = col + col_offset
                if target_row >= 3 or target_col >= 3:
                    valid_translation = False
                    break
                translated_pattern[(target_row, target_col)] = value

            if not valid_translation:
                continue

            if set(translated_pattern.keys()) != set(grid_cells.keys()):
                continue

            if all(grid_cells[position] == translated_pattern[position] for position in translated_pattern):
                return True, (row_offset, col_offset)

    return False, None


def find_matching_recipe(grid, recipes):
    """Sucht das erste passende Rezept für den aktuellen Crafting-Grid."""
    for result_item, recipe in recipes.items():
        if isinstance(recipe, list):
            if not recipe:
                continue
            recipe = recipe[0]

        if isinstance(recipe, dict):
            pattern = recipe.get("pattern")
            output_count = int(recipe.get("count", 1))
        else:
            pattern = recipe
            output_count = 1

        if pattern is None:
            continue

        matched, offset = matches_pattern(grid, pattern)
        if matched:
            return result_item, pattern, max(1, output_count), offset

    return None, None, 0, None
