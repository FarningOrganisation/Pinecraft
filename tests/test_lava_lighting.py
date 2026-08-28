import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from blocks import AIR
from lava_lighting import collect_lava_light_samples
from world import World


class LavaLightingSamplingTests(unittest.TestCase):
    def test_interior_pool_cells_do_not_emit_samples(self):
        world = World(seed=1)
        y0 = 24
        for x in range(0, 5):
            for y in range(y0, y0 + 5):
                world.set_block(x, y, AIR)
                world.set_lava(x, y, 1.0)

        samples = collect_lava_light_samples(
            world,
            min_tile_x=-2,
            max_tile_x=8,
            min_tile_y=20,
            max_tile_y=32,
            camera_world_x=2.5 * 32.0,
            camera_world_y=26.5 * 32.0,
            max_samples=64,
            sample_spacing=1,
            min_volume=0.2,
        )

        sample_tiles = {(sample.tile_x, sample.tile_y) for sample in samples}
        self.assertNotIn((2, y0 + 2), sample_tiles)
        self.assertIn((0, y0), sample_tiles)

    def test_only_visible_lava_is_considered(self):
        world = World(seed=1)
        world.set_block(1, 24, AIR)
        world.set_block(20, 24, AIR)
        world.set_lava(1, 24, 1.0)
        world.set_lava(20, 24, 1.0)

        samples = collect_lava_light_samples(
            world,
            min_tile_x=-2,
            max_tile_x=6,
            min_tile_y=20,
            max_tile_y=30,
            camera_world_x=2.0 * 32.0,
            camera_world_y=24.0 * 32.0,
            max_samples=16,
            sample_spacing=1,
            min_volume=0.2,
        )

        sample_tiles = {(sample.tile_x, sample.tile_y) for sample in samples}
        self.assertIn((1, 24), sample_tiles)
        self.assertNotIn((20, 24), sample_tiles)

    def test_cap_prioritizes_samples_nearest_camera(self):
        world = World(seed=1)
        for x in range(-12, 13):
            world.set_block(x, 24, AIR)
            world.set_lava(x, 24, 1.0)

        samples = collect_lava_light_samples(
            world,
            min_tile_x=-20,
            max_tile_x=20,
            min_tile_y=20,
            max_tile_y=30,
            camera_world_x=0.0,
            camera_world_y=24.0 * 32.0,
            max_samples=4,
            sample_spacing=1,
            min_volume=0.2,
        )

        self.assertEqual(len(samples), 4)
        distances = [abs(sample.world_x - 0.0) for sample in samples]
        self.assertEqual(distances, sorted(distances))

    def test_vertical_lava_fall_emits_samples_with_spacing(self):
        world = World(seed=1)
        for y in range(16, 34):
            world.set_block(0, y, AIR)
            world.set_lava(0, y, 1.0)

        samples = collect_lava_light_samples(
            world,
            min_tile_x=-2,
            max_tile_x=2,
            min_tile_y=12,
            max_tile_y=36,
            camera_world_x=0.0,
            camera_world_y=24.0 * 32.0,
            max_samples=16,
            sample_spacing=3,
            min_volume=0.2,
        )

        self.assertGreater(len(samples), 0)
        self.assertLess(len(samples), 16)

    def test_low_meaningful_lava_still_emits_dim_light(self):
        world = World(seed=1)
        y = 24
        world.set_block(0, y, AIR)
        world.set_block(1, y, AIR)
        world.set_lava(0, y, 0.03)

        samples = collect_lava_light_samples(
            world,
            min_tile_x=-2,
            max_tile_x=4,
            min_tile_y=20,
            max_tile_y=30,
            camera_world_x=0.0,
            camera_world_y=y * 32.0,
            max_samples=8,
            sample_spacing=1,
        )

        self.assertEqual(len(samples), 1)
        sample = samples[0]
        self.assertAlmostEqual(sample.strength, math.sqrt(0.03), places=6)
        self.assertGreater(sample.radius, 0.0)

    def test_microscopic_lava_below_cutoff_emits_no_light(self):
        world = World(seed=1)
        y = 24
        world.set_block(0, y, AIR)
        world.set_block(1, y, AIR)
        world.set_lava(0, y, 0.015)

        samples = collect_lava_light_samples(
            world,
            min_tile_x=-2,
            max_tile_x=4,
            min_tile_y=20,
            max_tile_y=30,
            camera_world_x=0.0,
            camera_world_y=y * 32.0,
            max_samples=8,
            sample_spacing=1,
        )

        self.assertEqual(len(samples), 0)


if __name__ == "__main__":
    unittest.main()
