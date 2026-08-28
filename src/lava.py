"""Lava-specific compatibility layer built on top of the generic liquid system."""

from __future__ import annotations

from blocks import is_block_water_passable
from liquids import LiquidConfig, LiquidSystem

MAX_LAVA = 1.0
MIN_LAVA = 0.001
MIN_LAVA_FLOW = 0.01
LAVA_HORIZONTAL_FLOW_FACTOR = 0.10
LAVA_TICK_RATE = 5
LAVA_TICK_INTERVAL = 1.0 / LAVA_TICK_RATE
MAX_LAVA_UPDATES_PER_TICK = 300
DEBUG_LAVA_PROFILE = True
PLAYER_LAVA_THRESHOLD = 0.05
LAVA_DAMAGE_INTERVAL = 0.5
LAVA_DAMAGE = 2

LAVA_CONFIG = LiquidConfig(
    max_liquid=MAX_LAVA,
    min_liquid=MIN_LAVA,
    min_flow=MIN_LAVA_FLOW,
    horizontal_flow_factor=LAVA_HORIZONTAL_FLOW_FACTOR,
    tick_rate=LAVA_TICK_RATE,
    max_updates_per_tick=MAX_LAVA_UPDATES_PER_TICK,
    debug_profile=DEBUG_LAVA_PROFILE,
)


class LavaSystem(LiquidSystem):
    """Lava-Simulation, implementiert über das generische LiquidSystem."""

    def __init__(self) -> None:
        super().__init__(
            config=LAVA_CONFIG,
            get_amount=lambda world, world_x, y: world.get_lava(world_x, y),
            set_amount=lambda world, world_x, y, amount: world.set_lava(world_x, y, amount),
            chunk_storage_attr="lava",
            passable_predicate=is_block_water_passable,
            debug_label="lava",
        )

    def activate_lava_column_above(self, world, world_x: int, start_y: int) -> None:
        """Kompatibilitäts-API: aktiviert Lavazellen oberhalb einer Blockänderung."""
        self.activate_liquid_column_above(world, world_x, start_y)

    def activate_loaded_chunk_lava(self, world, chunk_x: int) -> None:
        """Kompatibilitäts-API: reaktiviert potenziell instabile Lava beim Laden."""
        self.activate_loaded_chunk_liquid(world, chunk_x)
