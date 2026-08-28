import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from blocks import AIR, STONE
from lighting import LightingSystem
from settings import CHUNK_WIDTH, TILE_SIZE, WORLD_HEIGHT
from world import World


class LightingBackgroundBlendTests(unittest.TestCase):
    def _make_lighting_stub(self, world: World, tile_x: int, tile_y: int) -> LightingSystem:
        lighting = LightingSystem.__new__(LightingSystem)
        lighting.window = SimpleNamespace(
            world=world,
            player=SimpleNamespace(center_x=(tile_x + 0.5) * TILE_SIZE, center_y=(tile_y + 0.5) * TILE_SIZE),
        )
        return lighting

    def test_unloaded_columns_are_ignored_for_sky_blend(self):
        world = World(seed=1, load_radius=0, unload_radius=0)
        world.update_loaded_chunks(0.5 * TILE_SIZE)

        chunk = world.chunks[0]
        for y in range(WORLD_HEIGHT):
            for local_x in range(CHUNK_WIDTH):
                chunk.set_block(local_x, y, STONE)

        lighting = self._make_lighting_stub(world, tile_x=8, tile_y=12)

        blend = lighting.sky_background_blend()

        self.assertAlmostEqual(blend, 1.0, places=6)

    def test_loaded_open_air_still_reduces_sky_blend(self):
        world = World(seed=1, load_radius=0, unload_radius=0)
        world.update_loaded_chunks(0.5 * TILE_SIZE)

        chunk = world.chunks[0]
        for y in range(WORLD_HEIGHT):
            for local_x in range(CHUNK_WIDTH):
                chunk.set_block(local_x, y, STONE)

        tile_x = 8
        tile_y = 12
        for y in range(WORLD_HEIGHT):
            chunk.set_block(tile_x, y, AIR)

        lighting = self._make_lighting_stub(world, tile_x=tile_x, tile_y=tile_y)

        blend = lighting.sky_background_blend()

        self.assertLess(blend, 0.05)


if __name__ == "__main__":
    unittest.main()
