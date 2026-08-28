"""Generic liquid simulation and active-cell scheduler for Pinecraft."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from blocks import is_block_water_passable
from settings import CHUNK_WIDTH, WORLD_HEIGHT

if TYPE_CHECKING:
    from world import World


@dataclass(frozen=True)
class LiquidConfig:
    """Configuration values for one liquid simulation instance."""

    max_liquid: float = 1.0
    min_liquid: float = 0.001
    min_flow: float = 0.01
    horizontal_flow_factor: float = 0.25
    tick_rate: int = 15
    max_updates_per_tick: int = 500
    debug_profile: bool = True

    @property
    def tick_interval(self) -> float:
        return 1.0 / float(self.tick_rate)


class LiquidSystem:
    """Generic liquid simulation with snapshot + delta-buffer semantics."""

    def __init__(
        self,
        *,
        config: LiquidConfig,
        get_amount: Callable[[World, int, int], float],
        set_amount: Callable[[World, int, int, float], float],
        chunk_storage_attr: str,
        passable_predicate: Callable[[int], bool] = is_block_water_passable,
        debug_label: str = "liquid",
    ) -> None:
        self.max_water = config.max_liquid
        self.min_water = config.min_liquid
        self.min_flow = config.min_flow
        self.horizontal_flow_factor = config.horizontal_flow_factor
        self.max_updates_per_tick = config.max_updates_per_tick
        self.debug_profile = config.debug_profile
        self.debug_label = debug_label

        self._get_amount = get_amount
        self._set_amount = set_amount
        self._chunk_storage_attr = chunk_storage_attr
        self._is_passable = passable_predicate

        self._tick = 0
        self.active_cells: set[tuple[int, int]] = set()
        self.debug_last_tick: dict[str, float | int] = {
            "liquid_before": 0.0,
            "liquid_after": 0.0,
            "liquid_difference": 0.0,
            "active_cells": 0,
            "processed_cells": 0,
            "changed_cells": 0,
            "duration_ms": 0.0,
        }

    @staticmethod
    def _world_x_to_chunk_x(world_x: int) -> int:
        chunk_x, local_x = divmod(world_x, CHUNK_WIDTH)
        if local_x < 0:
            chunk_x -= 1
        return chunk_x

    def _amount(self, world: World, world_x: int, y: int) -> float:
        return float(self._get_amount(world, world_x, y))

    def _set(self, world: World, world_x: int, y: int, amount: float) -> float:
        return float(self._set_amount(world, world_x, y, amount))

    def activate_neighborhood(self, world_x: int, y: int) -> None:
        """Activates the local 4-neighborhood for potential re-simulation."""
        for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
            cell = (world_x + dx, y + dy)
            if y + dy < 0 or y + dy >= WORLD_HEIGHT:
                continue
            self.active_cells.add(cell)

    def activate_liquid_column_above(self, world: World, world_x: int, start_y: int) -> None:
        """Activates liquid cells above a changed block in the same column."""
        y = max(0, start_y)
        while y < WORLD_HEIGHT:
            block_id = world.get_block(world_x, y, generate_if_missing=False)
            if not self._is_passable(block_id):
                break

            if self._amount(world, world_x, y) > 0.0:
                self.activate_neighborhood(world_x, y)

            y += 1

    def deactivate_unloaded_chunks(self, loaded_chunk_xs: set[int]) -> None:
        """Removes active cells from chunks that are not loaded."""
        self.active_cells = {
            cell for cell in self.active_cells if self._world_x_to_chunk_x(cell[0]) in loaded_chunk_xs
        }

    def activate_loaded_chunk_liquid(self, world: World, chunk_x: int) -> None:
        """Re-activates potentially unstable liquid cells when a chunk is loaded."""
        chunk = world.chunks.get(chunk_x)
        if chunk is None:
            return

        liquid_storage = getattr(chunk, self._chunk_storage_attr)
        for (local_x, y), amount in liquid_storage.items():
            if amount <= 0.0:
                continue
            world_x = chunk_x * chunk.width + local_x

            on_chunk_edge = local_x == 0 or local_x == (chunk.width - 1)
            below_open = self._is_passable(world.get_block(world_x, y - 1, generate_if_missing=False))
            left_open = self._is_passable(world.get_block(world_x - 1, y, generate_if_missing=False))
            right_open = self._is_passable(world.get_block(world_x + 1, y, generate_if_missing=False))

            if on_chunk_edge or below_open or left_open or right_open:
                self.activate_neighborhood(world_x, y)

    def _active_liquid_cells(self, world: World) -> set[tuple[int, int]]:
        """Keeps only active cells that still contain liquid in loaded chunks."""
        return {
            cell
            for cell in self.active_cells
            if self._world_x_to_chunk_x(cell[0]) in world.chunks and self._amount(world, *cell) > 0.0
        }

    def _scan_active_cells(self, world: World) -> set[tuple[int, int]]:
        active: set[tuple[int, int]] = set()
        for chunk_x, chunk in world.chunks.items():
            liquid_storage = getattr(chunk, self._chunk_storage_attr)
            for (local_x, y), amount in liquid_storage.items():
                if amount > 0.0:
                    active.add((chunk_x * chunk.width + local_x, y))
        return active

    def _apply_changes(self, world: World, changes: dict[tuple[int, int], float]) -> None:
        """Applies delta-based changes after all flow calculations are complete."""
        if not changes:
            return
        for (world_x, y), delta in changes.items():
            if abs(delta) <= 1e-12:
                continue
            current = self._amount(world, world_x, y)
            updated = current + delta
            if updated <= 0.0:
                self._set(world, world_x, y, 0.0)
                continue
            self._set(world, world_x, y, max(0.0, min(self.max_water, updated)))

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
        """Processes liquid with snapshot + delta-buffer to preserve total amount."""
        del delta_time
        import time

        start = time.perf_counter()
        self._tick += 1

        current_active = self._active_liquid_cells(world)
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

        state = {cell: self._amount(world, *cell) for cell in current_active if self._amount(world, *cell) > 0.0}
        next_state = dict(state)
        moved_cells: set[tuple[int, int]] = set()

        def open_to_liquid(pos: tuple[int, int]) -> bool:
            if pos[1] < 0 or pos[1] >= WORLD_HEIGHT:
                return False

            chunk_x, local_x = divmod(pos[0], CHUNK_WIDTH)
            if local_x < 0:
                chunk_x -= 1
                local_x += CHUNK_WIDTH

            chunk = world.chunks.get(chunk_x)
            if chunk is None:
                return False
            return self._is_passable(chunk.get_block(local_x, pos[1]))

        def open_for_horizontal(pos: tuple[int, int]) -> bool:
            if not open_to_liquid(pos):
                return False
            if self._amount(world, *pos) > 0.0:
                return True
            return pos in activation_frontier

        for cell in sorted(current_active):
            amount = next_state.get(cell, 0.0)
            if amount <= 0.0:
                continue
            below = (cell[0], cell[1] - 1)
            if not open_to_liquid(below):
                continue
            below_amount = next_state.get(below, self._amount(world, *below))
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
                left_amount = next_state.get(left, self._amount(world, *left)) + horizontal_deltas.get(left, 0.0)
                right_amount = next_state.get(right, self._amount(world, *right)) + horizontal_deltas.get(right, 0.0)

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
            base_amount = next_state.get(pos, self._amount(world, *pos))
            next_state[pos] = max(0.0, min(self.max_water, base_amount + delta))

        changes: dict[tuple[int, int], float] = {}
        for pos in sorted(set(state) | set(next_state)):
            before = self._amount(world, *pos)
            after = next_state.get(pos, 0.0)
            delta = after - before
            if abs(delta) > 1e-12:
                changes[pos] = delta

        processed = len(current_active)
        if changes:
            for (world_x, y), delta in changes.items():
                current = self._amount(world, world_x, y)
                updated = current + delta
                if updated < self.min_water:
                    self._set(world, world_x, y, 0.0)
                    continue
                self._set(world, world_x, y, max(0.0, min(self.max_water, updated)))

            self.active_cells = {
                cell
                for cell in moved_cells
                if self._amount(world, *cell) > 0.0
            }
            for world_x, y in list(self.active_cells):
                for neighbor in ((world_x - 1, y), (world_x + 1, y)):
                    if self._amount(world, *neighbor) > 0.0:
                        self.active_cells.add(neighbor)
        else:
            self.active_cells = set()

        self.active_cells = {
            cell for cell in self.active_cells if self._amount(world, *cell) > 0.0
        }
        self.active_cells.update(deferred_active)

        duration_ms = (time.perf_counter() - start) * 1000.0
        self.debug_last_tick = {
            "liquid_before": 0.0,
            "liquid_after": 0.0,
            "liquid_difference": 0.0,
            "active_cells": int(active_before),
            "processed_cells": int(processed),
            "changed_cells": int(len(changes)),
            "duration_ms": float(duration_ms),
        }
        if self.debug_profile and self._tick % 30 == 0:
            print(
                f"[{self.debug_label}-profile] active="
                f"{active_before} processed={processed} changed={len(changes)} "
                f"ms={duration_ms:.3f}"
            )
