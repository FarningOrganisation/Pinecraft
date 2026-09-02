"""Hilfsfunktionen für die Crafting-Rezept-Erkennung."""

from itertools import product

from blocks import AIR, BLOCKS, get_foreground_block_id


def _canonicalize_grid_value(value):
    """Normalisiert Grid-Werte für Rezeptvergleiche.

    Hintergrund-Blockvarianten (Name endet auf " Background") werden auf ihre
    normale Block-ID gemappt, damit Crafting robust gegenüber der
    Block/Background-Konvertierung bleibt.
    """
    if value == AIR:
        return AIR

    block_definition = BLOCKS.get(value)
    if block_definition is None:
        return value

    name = str(block_definition.get("name", ""))
    if not name.endswith(" Background"):
        return value

    foreground_id = get_foreground_block_id(value)
    return foreground_id if foreground_id is not None else value


def _non_air_cells(grid):
    """Gibt alle nicht-leeren Zellen als {(row, col): item_id} zurück."""
    return {
        (row_index, col_index): _canonicalize_grid_value(value)
        for row_index, row in enumerate(grid)
        for col_index, value in enumerate(row)
        if value != AIR
    }


def _normalize_pattern(pattern):
    """Normalisiert ein Rezeptmuster zu einer rechteckigen Matrix mit AIR-Fill."""
    if not isinstance(pattern, list) or not pattern:
        return None
    if any(not isinstance(row, list) for row in pattern):
        return None

    width = max((len(row) for row in pattern), default=0)
    height = len(pattern)
    if width <= 0:
        return None
    if width > 3 or height > 3:
        return None

    normalized = []
    for row in pattern:
        normalized.append(row + [AIR] * (width - len(row)))
    return normalized


def _iter_normalized_patterns(pattern):
    """Erzeugt alle gültigen AIR-normalisierten Varianten eines Rezeptmusters.

    Reihen ohne explizites AIR dürfen horizontal innerhalb der Musterbreite gleiten.
    So koennen Rezepte kompakt ohne AIR-Placeholder notiert werden.
    """
    if not isinstance(pattern, list) or not pattern:
        return []
    if any(not isinstance(row, list) for row in pattern):
        return []

    width = max((len(row) for row in pattern), default=0)
    height = len(pattern)
    if width <= 0 or width > 3 or height > 3:
        return []

    row_starts = []
    for row in pattern:
        row_len = len(row)
        if row_len == 0:
            row_starts.append([0])
            continue

        max_start = width - row_len
        if max_start < 0:
            return []

        # Enthält die Zeile explizites AIR, bleiben Positionen exakt erhalten.
        if AIR in row:
            row_starts.append([0])
        else:
            row_starts.append(list(range(max_start + 1)))

    normalized_variants = []
    for starts in product(*row_starts):
        normalized = []
        for row_index, row in enumerate(pattern):
            start = starts[row_index]
            left_air = [AIR] * start
            right_air = [AIR] * (width - start - len(row))
            normalized.append(left_air + row + right_air)
        normalized_variants.append(normalized)

    return normalized_variants


def matches_pattern(grid, pattern):
    """Prüft, ob ein Rezept-Muster an beliebiger Position im 3x3-Grid passt."""
    if len(grid) != 3 or any(len(row) != 3 for row in grid):
        return False, None, None

    grid_cells = _non_air_cells(grid)

    for normalized_pattern in _iter_normalized_patterns(pattern):
        pattern_cells = _non_air_cells(normalized_pattern)

        if not pattern_cells:
            return (not grid_cells), (0, 0), normalized_pattern
        if len(grid_cells) != len(pattern_cells):
            continue

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
                    return True, (row_offset, col_offset), normalized_pattern

    return False, None, None


def find_matching_recipe(grid, recipes):
    """Sucht das erste passende Rezept für den aktuellen Crafting-Grid."""
    if not isinstance(recipes, dict):
        return None, None, 0, None

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

        if not _iter_normalized_patterns(pattern):
            continue

        matched, offset, matched_pattern = matches_pattern(grid, pattern)
        if matched:
            return result_item, matched_pattern, max(1, output_count), offset

    return None, None, 0, None
