"""Water/lava interaction detection helpers for Pinecraft."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blocks import AIR, OBSIDIAN

if TYPE_CHECKING:
    from world import World

LIQUID_REACTION_THRESHOLD = 0.05


class LiquidInteractionSystem:
    """Detects meaningful water/lava contacts around changed cells."""

    def __init__(self, reaction_threshold: float = LIQUID_REACTION_THRESHOLD) -> None:
        self.reaction_threshold = reaction_threshold

    def _cell_has_contact(self, world: World, x: int, y: int) -> bool:
        threshold = self.reaction_threshold
        water_here = world.get_water(x, y)
        lava_here = world.get_lava(x, y)

        if water_here >= threshold and lava_here >= threshold:
            return True

        if water_here >= threshold:
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if world.get_lava(nx, ny) >= threshold:
                    return True

        if lava_here >= threshold:
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if world.get_water(nx, ny) >= threshold:
                    return True

        return False

    def _lava_cell_has_contact(self, world: World, x: int, y: int) -> bool:
        """True, wenn Lava in dieser Zelle über Schwellwert liegt und Wasser berührt."""
        threshold = self.reaction_threshold
        if world.get_lava(x, y) < threshold:
            return False

        if world.get_water(x, y) >= threshold:
            return True

        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if world.get_water(nx, ny) >= threshold:
                return True
        return False

    def detect_contacts(
        self,
        world: World,
        changed_water: list[tuple[int, int, float, float]],
        changed_lava: list[tuple[int, int, float, float]],
        changed_blocks: list[tuple[int, int, int, int]],
    ) -> list[tuple[int, int]]:
        """Checks only changed regions and immediate neighbors for water/lava contact."""
        candidate_cells: set[tuple[int, int]] = set()

        for x, y, _old, _new in changed_water:
            candidate_cells.add((x, y))
        for x, y, _old, _new in changed_lava:
            candidate_cells.add((x, y))
        for x, y, _old, _new in changed_blocks:
            candidate_cells.add((x, y))

        if not candidate_cells:
            return []

        expanded_cells: set[tuple[int, int]] = set()
        for x, y in candidate_cells:
            expanded_cells.add((x, y))
            expanded_cells.add((x - 1, y))
            expanded_cells.add((x + 1, y))
            expanded_cells.add((x, y - 1))
            expanded_cells.add((x, y + 1))

        contacts: set[tuple[int, int]] = set()
        for x, y in expanded_cells:
            if self._cell_has_contact(world, x, y):
                contacts.add((x, y))

        if contacts:
            # Milestone 6 debug output: contact detection only, no reactions yet.
            print("WATER/LAVA CONTACT")

        return sorted(contacts)

    def resolve_contacts(self, world: World, contacts: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """Wandelt kontaktierende Lavazellen in Obsidian um und entfernt die Lava."""
        if not contacts:
            return []

        candidate_lava_cells: set[tuple[int, int]] = set()
        for x, y in contacts:
            candidate_lava_cells.add((x, y))
            candidate_lava_cells.add((x - 1, y))
            candidate_lava_cells.add((x + 1, y))
            candidate_lava_cells.add((x, y - 1))
            candidate_lava_cells.add((x, y + 1))

        resolved: set[tuple[int, int]] = set()
        for x, y in candidate_lava_cells:
            if not self._lava_cell_has_contact(world, x, y):
                continue

            if world.get_block(x, y) != AIR:
                world.set_lava(x, y, 0.0)
                continue

            world.set_block(x, y, OBSIDIAN)
            resolved.add((x, y))

        return sorted(resolved)
