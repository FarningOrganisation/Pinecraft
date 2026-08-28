import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from world import World
from world_generation import UNDERGROUND_LAVA_MAX_Y, UNDERGROUND_WATER_MAX_Y


class LavaGenerationTests(unittest.TestCase):
    def _count_band(self, liquid_map, min_y: int, max_y: int) -> int:
        return sum(1 for (_local_x, y), amount in liquid_map.items() if amount > 0.0 and min_y <= y <= max_y)

    def test_underground_generation_contains_both_water_and_lava(self):
        world = World(seed=1)
        for chunk_x in range(-8, 9):
            world.generate_chunk(chunk_x)

        total_water = 0
        total_lava = 0
        for chunk in world.chunks.values():
            total_water += sum(1 for amount in chunk.water.values() if amount > 0.0)
            total_lava += sum(1 for amount in chunk.lava.values() if amount > 0.0)

        self.assertGreater(total_water, 0)
        self.assertGreater(total_lava, 0)

    def test_water_is_more_common_at_medium_depth_than_deep(self):
        world = World(seed=1)
        for chunk_x in range(-8, 9):
            world.generate_chunk(chunk_x)

        medium_min_y = 56
        medium_max_y = min(UNDERGROUND_WATER_MAX_Y, 104)
        deep_min_y = 6
        deep_max_y = 44

        medium_water = 0
        deep_water = 0
        for chunk in world.chunks.values():
            medium_water += self._count_band(chunk.water, medium_min_y, medium_max_y)
            deep_water += self._count_band(chunk.water, deep_min_y, deep_max_y)

        self.assertGreater(medium_water, deep_water)

    def test_lava_is_more_common_at_deep_depth_than_medium(self):
        world = World(seed=1)
        for chunk_x in range(-8, 9):
            world.generate_chunk(chunk_x)

        deep_min_y = 6
        deep_max_y = min(UNDERGROUND_LAVA_MAX_Y, 44)
        medium_min_y = 56
        medium_max_y = min(UNDERGROUND_LAVA_MAX_Y, 74)

        deep_lava = 0
        medium_lava = 0
        for chunk in world.chunks.values():
            deep_lava += self._count_band(chunk.lava, deep_min_y, deep_max_y)
            medium_lava += self._count_band(chunk.lava, medium_min_y, medium_max_y)

        self.assertGreater(deep_lava, medium_lava)

    def test_no_cell_contains_water_and_lava_at_generation(self):
        world = World(seed=1)
        for chunk_x in range(-8, 9):
            world.generate_chunk(chunk_x)

        for chunk in world.chunks.values():
            overlap = set(chunk.water.keys()) & set(chunk.lava.keys())
            self.assertEqual(overlap, set())


if __name__ == "__main__":
    unittest.main()
