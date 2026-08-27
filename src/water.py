"""Water simulation and active-cell scheduler for Pinecraft."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blocks import is_block_water_passable
from settings import CHUNK_WIDTH, WORLD_HEIGHT

if TYPE_CHECKING:
    from world import World

MAX_WATER = 1.0
MIN_WATER = 0.001
MIN_FLOW = 0.01
DAMPED_HORIZONTAL_FLOW_FACTOR = 0.25
WATER_TICK_RATE = 15
WATER_TICK_INTERVAL = 1.0 / WATER_TICK_RATE
MAX_WATER_UPDATES_PER_TICK = 500
DEBUG_WATER_PROFILE = True


class WaterSystem:
    """Wasser-Simulation mit Snapshot + Delta-Buffer."""

    def __init__(self) -> None:
        self.max_water = MAX_WATER
        self.min_water = MIN_WATER
        self.min_flow = MIN_FLOW
        self.horizontal_flow_factor = DAMPED_HORIZONTAL_FLOW_FACTOR
        self.max_updates_per_tick = MAX_WATER_UPDATES_PER_TICK
        self._tick = 0
        self.active_cells: set[tuple[int, int]] = set()
        self.debug_last_tick: dict[str, float | int] = {
            "water_before": 0.0,
            "water_after": 0.0,
            "water_difference": 0.0,
            "active_cells": 0,
            "processed_cells": 0,
            "changed_cells": 0,
            "duration_ms": 0.0,
        }

    def activate_neighborhood(self, world_x: int, y: int) -> None:
        """Aktiviert nur die unmittelbare Nachbarschaft eines geänderten Wasserfelds."""
        for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
            cell = (world_x + dx, y + dy)
            if y + dy < 0 or y + dy >= WORLD_HEIGHT:
                continue
            self.active_cells.add(cell)

    @staticmethod
    def _world_x_to_chunk_x(world_x: int) -> int:
        chunk_x, local_x = divmod(world_x, CHUNK_WIDTH)
        if local_x < 0:
            chunk_x -= 1
        return chunk_x

    def deactivate_unloaded_chunks(self, loaded_chunk_xs: set[int]) -> None:
        """Entfernt aktive Zellen, deren Chunk derzeit nicht geladen ist."""
        self.active_cells = {
            cell for cell in self.active_cells if self._world_x_to_chunk_x(cell[0]) in loaded_chunk_xs
        }

    def activate_loaded_chunk_water(self, world: World, chunk_x: int) -> None:
        """Reaktiviert beim Laden nur potenziell instabile Wasserzellen."""
        chunk = world.chunks.get(chunk_x)
        if chunk is None:
            return
        for (local_x, y), amount in chunk.water.items():
            if amount <= 0.0:
                continue
            world_x = chunk_x * chunk.width + local_x

            on_chunk_edge = local_x == 0 or local_x == (chunk.width - 1)
            below_open = is_block_water_passable(world.get_block(world_x, y - 1, generate_if_missing=False))
            left_open = is_block_water_passable(world.get_block(world_x - 1, y, generate_if_missing=False))
            right_open = is_block_water_passable(world.get_block(world_x + 1, y, generate_if_missing=False))

            if on_chunk_edge or below_open or left_open or right_open:
                self.activate_neighborhood(world_x, y)

    def _active_water_cells(self, world: World) -> set[tuple[int, int]]:
        """Filtert die Aktivitätsmenge auf echte Wasserzellen, damit leere Nachbarfelder nicht weiterlaufen."""
        return {
            cell
            for cell in self.active_cells
            if self._world_x_to_chunk_x(cell[0]) in world.chunks and world.get_water(*cell) > 0.0
        }

    def _scan_active_cells(self, world: World) -> set[tuple[int, int]]:
        active: set[tuple[int, int]] = set()
        for chunk_x, chunk in world.chunks.items():
            for (local_x, y), amount in chunk.water.items():
                if amount > 0.0:
                    active.add((chunk_x * chunk.width + local_x, y))
        return active

    def _apply_changes(self, world: World, changes: dict[tuple[int, int], float]) -> None:
        """Wendet delta-basierte Änderungen nach Abschluss der Berechnung an."""
        if not changes:
            return
        for (world_x, y), delta in changes.items():
            if abs(delta) <= 1e-12:
                continue
            current = world.get_water(world_x, y)
            updated = current + delta
            if updated <= 0.0:
                world.set_water(world_x, y, 0.0)
                continue
            world.set_water(world_x, y, max(0.0, min(self.max_water, updated)))

    def _compute_horizontal_flow(self, left_amount: float, right_amount: float) -> float:
        """Returns signed damped flow from left to right (negative means right to left)."""
        difference = left_amount - right_amount
        if abs(difference) < self.min_flow:
            return 0.0

        if difference > 0.0:
            move = min(difference * self.horizontal_flow_factor, left_amount, self.max_water - right_amount)
            return move if move > 1e-12 else 0.0

        move = min((-difference) * self.horizontal_flow_factor, right_amount, self.max_water - left_amount)
        return -move if move > 1e-12 else 0.0

    def update(self, world: World, delta_time: float) -> None:
        """Verarbeitet Wasser mit Snapshot + Delta-Buffer, damit Gesamtmenge erhalten bleibt."""
        del delta_time
        import time

        start = time.perf_counter()
        self._tick += 1

        current_active = self._active_water_cells(world)
        if not current_active:
            self.active_cells = set()
            return

        activation_frontier = set(self.active_cells)
        for world_x, y in current_active:
            activation_frontier.add((world_x - 1, y))
            activation_frontier.add((world_x + 1, y))

        active_before = len(current_active)
        deferred_active: set[tuple[int, int]] = set()
        if len(current_active) > self.max_updates_per_tick:
            ordered = sorted(current_active)
            window = self.max_updates_per_tick
            offset = ((self._tick - 1) * window) % len(ordered)
            picked = ordered[offset : offset + window]
            if len(picked) < window:
                picked = picked + ordered[: window - len(picked)]
            current_active = set(picked)
            deferred_active = set(ordered) - current_active

        state = {cell: world.get_water(*cell) for cell in current_active if world.get_water(*cell) > 0.0}
        next_state = dict(state)
        moved_cells: set[tuple[int, int]] = set()

        def open_to_water(pos: tuple[int, int]) -> bool:
            if pos[1] < 0 or pos[1] >= WORLD_HEIGHT:
                return False

            chunk_x, local_x = divmod(pos[0], CHUNK_WIDTH)
            if local_x < 0:
                chunk_x -= 1
                local_x += CHUNK_WIDTH

            chunk = world.chunks.get(chunk_x)
            if chunk is None:
                return False
            return is_block_water_passable(chunk.get_block(local_x, pos[1]))

        def open_for_horizontal(pos: tuple[int, int]) -> bool:
            if not open_to_water(pos):
                return False
            if world.get_water(*pos) > 0.0:
                return True
            return pos in activation_frontier

        for cell in sorted(current_active):
            amount = next_state.get(cell, 0.0)
            if amount <= 0.0:
                continue
            below = (cell[0], cell[1] - 1)
            if not open_to_water(below):
                continue
            below_amount = next_state.get(below, world.get_water(*below))
            if below_amount >= self.max_water:
                continue
            flow = min(amount, self.max_water - below_amount)
            if flow > self.min_flow:
                next_state[cell] = amount - flow
                next_state[below] = below_amount + flow
                moved_cells.add(cell)
                moved_cells.add(below)

        processed_pairs: set[tuple[tuple[int, int], tuple[int, int]]] = set()
        horizontal_deltas: dict[tuple[int, int], float] = {}
        for cell in sorted(current_active):
            for dx in (-1, 1):
                neighbor = (cell[0] + dx, cell[1])
                if not open_for_horizontal(neighbor):
                    continue
                pair = (cell, neighbor) if cell <= neighbor else (neighbor, cell)
                if pair in processed_pairs:
                    continue
                processed_pairs.add(pair)

                left, right = pair
                left_amount = next_state.get(left, world.get_water(*left)) + horizontal_deltas.get(left, 0.0)
                right_amount = next_state.get(right, world.get_water(*right)) + horizontal_deltas.get(right, 0.0)

                flow = self._compute_horizontal_flow(left_amount, right_amount)
                if flow == 0.0:
                    continue

                horizontal_deltas[left] = horizontal_deltas.get(left, 0.0) - flow
                horizontal_deltas[right] = horizontal_deltas.get(right, 0.0) + flow
                moved_cells.add(left)
                moved_cells.add(right)

        for pos, delta in horizontal_deltas.items():
            if abs(delta) <= 1e-12:
                continue
            base_amount = next_state.get(pos, world.get_water(*pos))
            next_state[pos] = max(0.0, min(self.max_water, base_amount + delta))

        changes: dict[tuple[int, int], float] = {}
        for pos in sorted(set(state) | set(next_state)):
            before = world.get_water(*pos)
            after = next_state.get(pos, 0.0)
            delta = after - before
            if abs(delta) > 1e-12:
                changes[pos] = delta

        processed = len(current_active)
        if changes:
            for (world_x, y), delta in changes.items():
                current = world.get_water(world_x, y)
                updated = current + delta
                if updated < self.min_water:
                    world.set_water(world_x, y, 0.0)
                    continue
                world.set_water(world_x, y, max(0.0, min(self.max_water, updated)))

            self.active_cells = {
                cell
                for cell in moved_cells
                if world.get_water(*cell) > 0.0
            }
            for world_x, y in list(self.active_cells):
                for neighbor in ((world_x - 1, y), (world_x + 1, y)):
                    if world.get_water(*neighbor) > 0.0:
                        self.active_cells.add(neighbor)
        else:
            self.active_cells = set()

        self.active_cells = {
            cell for cell in self.active_cells if world.get_water(*cell) > 0.0
        }
        self.active_cells.update(deferred_active)

        duration_ms = (time.perf_counter() - start) * 1000.0
        self.debug_last_tick = {
            "water_before": 0.0,
            "water_after": 0.0,
            "water_difference": 0.0,
            "active_cells": int(active_before),
            "processed_cells": int(processed),
            "changed_cells": int(len(changes)),
            "duration_ms": float(duration_ms),
        }
        if DEBUG_WATER_PROFILE and self._tick % 30 == 0:
            print(
                "[water-profile] active="
                f"{active_before} processed={processed} changed={len(changes)} "
                f"ms={duration_ms:.3f}"
            )
