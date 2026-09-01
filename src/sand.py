"""Gemeinsame Hilfsfunktionen fuer Sand-/Fallblock-Verhalten."""

from __future__ import annotations

from collections.abc import Callable

SAND_SLIDE_CHANCE_SHALLOW = 0.10
SAND_SLIDE_CHANCE_MEDIUM = 0.30
SAND_SLIDE_CHANCE_STEEP = 0.50


def slide_probability(depth_score: int) -> float:
    """Liefert die Abrutsch-Wahrscheinlichkeit anhand der lokalen Steilheit."""
    if depth_score >= 3:
        return SAND_SLIDE_CHANCE_STEEP
    if depth_score >= 2:
        return SAND_SLIDE_CHANCE_MEDIUM
    return SAND_SLIDE_CHANCE_SHALLOW


def local_fall_depth(
    get_block: Callable[[int, int], int],
    x: int,
    y: int,
    *,
    max_probe: int = 6,
    air_block_id: int = 0,
) -> int:
    """Schaetzt, wie weit ein Block an einer X-Position weiter absacken kann."""
    depth = 0
    probe_y = y
    while probe_y > 0 and depth < max_probe:
        if get_block(x, probe_y - 1) != air_block_id:
            break
        depth += 1
        probe_y -= 1
    return depth


def slide_decision_signature(below_block: int, left_depth: int, right_depth: int) -> tuple[int, int, int]:
    """Signatur fuer stabile Sand-Entscheidung bis sich die Umgebung aendert."""
    return int(below_block), int(left_depth), int(right_depth)
