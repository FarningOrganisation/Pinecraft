"""Water-specific compatibility layer built on top of the generic liquid system."""

from __future__ import annotations

from blocks import is_block_water_passable
from liquids import LiquidConfig, LiquidSystem

MAX_WATER = 1.0
MIN_WATER = 0.001
MIN_FLOW = 0.01
DAMPED_HORIZONTAL_FLOW_FACTOR = 0.25
WATER_TICK_RATE = 15
WATER_TICK_INTERVAL = 1.0 / WATER_TICK_RATE
MAX_WATER_UPDATES_PER_TICK = 500
DEBUG_WATER_PROFILE = True

WATER_CONFIG = LiquidConfig(
    max_liquid=MAX_WATER,
    min_liquid=MIN_WATER,
    min_flow=MIN_FLOW,
    horizontal_flow_factor=DAMPED_HORIZONTAL_FLOW_FACTOR,
    tick_rate=WATER_TICK_RATE,
    max_updates_per_tick=MAX_WATER_UPDATES_PER_TICK,
    debug_profile=DEBUG_WATER_PROFILE,
)


class WaterSystem(LiquidSystem):
    """Wasser-Simulation, implementiert über das generische LiquidSystem."""

    def __init__(self) -> None:
        super().__init__(
            config=WATER_CONFIG,
            get_amount=lambda world, world_x, y: world.get_water(world_x, y),
            set_amount=lambda world, world_x, y, amount: world.set_water(world_x, y, amount),
            chunk_storage_attr="water",
            passable_predicate=is_block_water_passable,
            debug_label="water",
        )

    def activate_water_column_above(self, world, world_x: int, start_y: int) -> None:
        """Kompatibilitäts-API: aktiviert Wasserzellen oberhalb einer Blockänderung."""
        self.activate_liquid_column_above(world, world_x, start_y)

    def activate_loaded_chunk_water(self, world, chunk_x: int) -> None:
        """Kompatibilitäts-API: reaktiviert potenziell instabiles Wasser beim Laden."""
        self.activate_loaded_chunk_liquid(world, chunk_x)
