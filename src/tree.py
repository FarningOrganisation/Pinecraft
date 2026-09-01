"""Gemeinsame Baum-Layout-Logik für WorldGen und Runtime-Wachstum."""

from __future__ import annotations


def oak_trunk_height(seed: int, tile_x: int) -> int:
    """Deterministische Stammhöhe zwischen 4 und 6."""
    value = (tile_x * 83492791 + seed * 2971215073) & 0xFFFFFFFF
    return 4 + (value % 3)


def build_oak_tree_layout(
    tile_x: int,
    trunk_base_y: int,
    trunk_height: int,
    world_height: int,
) -> tuple[list[tuple[int, int]], set[tuple[int, int]], int]:
    """Erzeugt Stamm- und Blattpositionen einer Oak-Basisform."""
    effective_height = max(1, int(trunk_height))
    trunk_top = min(world_height - 2, trunk_base_y + effective_height - 1)

    trunk_positions = [(tile_x, trunk_y) for trunk_y in range(trunk_base_y, trunk_top + 1)]
    leaf_positions: set[tuple[int, int]] = set()
    leaf_center_y = trunk_top

    core_offsets = [(0, 0), (0, 1), (0, -1), (1, 0), (-1, 0)]
    for dx, dy in core_offsets:
        leaf_positions.add((tile_x + dx, leaf_center_y + dy))

    for dx in range(-2, 3):
        for dy in range(-2, 2):
            dist = abs(dx) + abs(dy)
            max_dist = 2 + (1 if dy < 0 else 0)
            if dist <= max_dist:
                leaf_positions.add((tile_x + dx, leaf_center_y + dy))

    leaf_positions.add((tile_x, leaf_center_y + 2))

    return trunk_positions, leaf_positions, trunk_top