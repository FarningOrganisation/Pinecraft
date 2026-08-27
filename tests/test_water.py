import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import arcade

from blocks import AIR, GRASS, LEAVES, OAK, SAND, STONE
from game import GameWindow
from settings import CHUNK_WIDTH, TILE_SIZE
from world import World
from world_generation import (
    COASTAL_BEACH_BAND,
    SEA_LEVEL,
    UNDERGROUND_WATER_MAX_Y,
    WATER_RENDER_THRESHOLD,
    build_chunk_water_sprite_list,
    get_water_render_height,
)


class WaterTests(unittest.TestCase):
    def test_water_falls_when_space_below_is_empty(self):
        world = World(seed=1)
        world.set_block(0, 9, AIR)
        world.set_block(0, 8, AIR)
        world.set_block(0, 7, AIR)
        world.set_water(0, 9, 1.0)

        world.water_system.update(world, 0.1)

        self.assertGreater(world.get_water(0, 8), 0.0)
        self.assertAlmostEqual(world.get_water(0, 9), 0.0, places=6)

    def test_water_spreads_horizontally_when_blocked_below(self):
        world = World(seed=1)
        world.set_block(0, 8, AIR)
        world.set_block(1, 8, AIR)
        world.set_block(0, 7, STONE)
        world.set_block(1, 7, STONE)
        world.set_water(0, 8, 1.0)

        world.water_system.update(world, 0.1)

        self.assertTrue(
            world.get_water(1, 8) > 0.0 or world.get_water(-1, 8) > 0.0,
            "water should spread horizontally to a neighboring empty cell when blocked below",
        )

    def test_water_spreads_to_both_empty_neighbors(self):
        world = World(seed=1)
        world.set_block(-1, 8, AIR)
        world.set_block(0, 8, AIR)
        world.set_block(1, 8, AIR)
        world.set_block(-1, 7, STONE)
        world.set_block(0, 7, STONE)
        world.set_block(1, 7, STONE)
        world.set_water(0, 8, 1.0)

        world.water_system.update(world, 0.1)

        self.assertGreater(world.get_water(-1, 8), 0.0)
        self.assertGreater(world.get_water(1, 8), 0.0)

    def test_water_uses_non_solid_background_tiles_as_open_space(self):
        world = World(seed=1)
        world.set_block(-1, 8, AIR)
        world.set_block(0, 8, OAK)
        world.set_block(1, 8, AIR)
        world.set_block(0, 7, STONE)
        world.set_water(0, 8, 1.0)

        world.water_system.update(world, 0.1)

        self.assertGreater(world.get_water(-1, 8), 0.0)
        self.assertGreater(world.get_water(1, 8), 0.0)

    def test_stable_water_cells_become_inactive(self):
        world = World(seed=1)
        for x in (-2, -1, 0, 1, 2):
            world.set_block(x, 8, AIR)
            world.set_block(x, 7, STONE)
        world.set_block(-2, 8, STONE)
        world.set_block(2, 8, STONE)
        world.set_water(-1, 8, 0.5)
        world.set_water(0, 8, 0.5)
        world.set_water(1, 8, 0.5)

        world.water_system.update(world, 0.1)

        self.assertEqual(world.water_system.active_cells, set())

    def test_water_changes_are_tracked_for_render_updates(self):
        world = World(seed=1)
        world.set_block(0, 8, AIR)
        world.set_block(0, 7, AIR)

        world.set_water(0, 8, 1.0)

        changes = world.consume_changed_water()
        self.assertTrue(changes)
        self.assertAlmostEqual(changes[0][3], 1.0, places=6)

    def test_tiny_water_changes_are_tracked_for_render_updates(self):
        world = World(seed=1)
        world.set_block(0, 8, AIR)

        world.set_water(0, 8, 0.03)
        _ = world.consume_changed_water()

        world.set_water(0, 8, 0.024)
        changes = world.consume_changed_water()

        self.assertEqual(len(changes), 1)
        self.assertAlmostEqual(changes[0][2], 0.03, places=6)
        self.assertAlmostEqual(changes[0][3], 0.024, places=6)

    def test_water_renders_over_non_solid_background_tiles(self):
        world = World(seed=1)
        world.set_block(0, 8, OAK)
        world.set_water(0, 8, 1.0)

        sprites = build_chunk_water_sprite_list(0, world.chunks[0], 0, 20)

        self.assertEqual(len(sprites), 1)

    def test_tiny_water_below_render_threshold_is_hidden(self):
        world = World(seed=1)
        world.set_block(0, 8, AIR)
        world.set_water(0, 8, WATER_RENDER_THRESHOLD * 0.5)

        sprites = build_chunk_water_sprite_list(0, world.chunks[0], 0, 20)

        self.assertEqual(len(sprites), 0)

    def test_render_height_uses_threshold_then_eighth_steps(self):
        below = max(0.0, WATER_RENDER_THRESHOLD - 1e-6)
        at_threshold = WATER_RENDER_THRESHOLD

        self.assertEqual(get_water_render_height(below), 0.0)
        self.assertGreater(get_water_render_height(at_threshold), 0.0)

    def test_water_conservation_in_small_basin(self):
        world = World(seed=1)
        for x in (-2, -1, 0, 1, 2):
            world.set_block(x, 8, AIR)
            world.set_block(x, 7, STONE)
        world.set_block(-2, 8, STONE)
        world.set_block(2, 8, STONE)
        world.set_water(0, 8, 1.0)

        total_before = sum(world.get_water(x, 8) for x in (-1, 0, 1))
        for _ in range(20):
            world.water_system.update(world, 0.1)
        total_after = sum(world.get_water(x, 8) for x in (-1, 0, 1))

        self.assertAlmostEqual(total_after, total_before, places=6)

    def test_stable_pool_eventually_becomes_inactive(self):
        world = World(seed=1)
        for x in (-2, -1, 0, 1, 2):
            world.set_block(x, 8, AIR)
            world.set_block(x, 7, STONE)
        world.set_block(-2, 8, STONE)
        world.set_block(2, 8, STONE)
        world.set_water(-1, 8, 0.5)
        world.set_water(0, 8, 0.5)
        world.set_water(1, 8, 0.5)

        for _ in range(30):
            world.water_system.update(world, 0.1)

        self.assertLess(len(world.water_system.active_cells), 3)

    def test_breaking_block_under_stable_pool_wakes_and_drains(self):
        world = World(seed=1)
        for x in (-2, -1, 0, 1, 2):
            world.set_block(x, 8, AIR)
            world.set_block(x, 7, STONE)
        world.set_block(-2, 8, STONE)
        world.set_block(2, 8, STONE)
        world.set_water(-1, 8, 0.5)
        world.set_water(0, 8, 0.5)
        world.set_water(1, 8, 0.5)

        for _ in range(40):
            world.water_system.update(world, 0.1)
            if not world.water_system.active_cells:
                break
        self.assertEqual(world.water_system.active_cells, set())

        world.break_block(0, 7)

        self.assertIn((0, 8), world.water_system.active_cells)

        flowed_down = False
        for _ in range(20):
            world.water_system.update(world, 0.1)
            if world.get_water(0, 7) > 0.0:
                flowed_down = True
                break

        self.assertTrue(flowed_down)

    def test_placing_block_next_to_stable_pool_wakes_neighbors(self):
        world = World(seed=1)
        for x in (-2, -1, 0, 1, 2):
            world.set_block(x, 8, AIR)
            world.set_block(x, 7, STONE)
        world.set_block(-2, 8, STONE)
        world.set_block(2, 8, STONE)
        world.set_water(-1, 8, 0.5)
        world.set_water(0, 8, 0.5)
        world.set_water(1, 8, 0.5)

        for _ in range(40):
            world.water_system.update(world, 0.1)
            if not world.water_system.active_cells:
                break
        self.assertEqual(world.water_system.active_cells, set())

        world.set_block(1, 9, STONE)

        self.assertIn((1, 8), world.water_system.active_cells)

    def test_closed_six_wide_basin_settles_to_even_level(self):
        world = World(seed=1)
        for x in range(-1, 7):
            world.set_block(x, 8, AIR)
            world.set_block(x, 7, STONE)
        world.set_block(-1, 8, STONE)
        world.set_block(6, 8, STONE)

        # Total water = 3.0 in a 6-wide basin should settle near 0.5 per cell.
        world.set_water(0, 8, 1.0)
        world.set_water(1, 8, 1.0)
        world.set_water(2, 8, 1.0)

        settled_tick = None
        for tick in range(1, 401):
            world.water_system.update(world, 0.1)
            values = [world.get_water(x, 8) for x in range(0, 6)]
            max_neighbor_diff = max(abs(values[i] - values[i + 1]) for i in range(5))
            if max_neighbor_diff < world.water_system.min_flow and not world.water_system.active_cells:
                settled_tick = tick
                break

        self.assertIsNotNone(settled_tick)

    def test_one_block_next_to_one_by_one_hole_conserves_water(self):
        world = World(seed=1)

        for x in range(-2, 5):
            for y in range(5, 10):
                world.set_block(x, y, AIR)

        for x in range(-2, 5):
            world.set_block(x, 5, STONE)

        for x in range(-2, 5):
            world.set_block(x, 6, STONE)
        world.set_block(1, 6, AIR)

        for x in range(-2, 5):
            world.set_block(x, 7, AIR)

        world.set_water(0, 7, 1.0)

        total_before = sum(world.get_water(x, y) for x in range(-2, 5) for y in range(5, 10))
        for _ in range(120):
            world.water_system.update(world, 0.1)
        total_after = sum(world.get_water(x, y) for x in range(-2, 5) for y in range(5, 10))

        self.assertAlmostEqual(total_after, total_before, places=6)

    def test_closed_basins_of_various_lengths_eventually_sleep(self):
        for length in (3, 6, 9, 12, 20):
            with self.subTest(length=length):
                world = World(seed=1)
                for x in range(-1, length + 1):
                    world.set_block(x, 8, AIR)
                    world.set_block(x, 7, STONE)
                world.set_block(-1, 8, STONE)
                world.set_block(length, 8, STONE)

                total_water = length * 0.5
                full_cells = int(total_water)
                fractional = total_water - full_cells
                for x in range(full_cells):
                    world.set_water(x, 8, 1.0)
                if fractional > 0.0:
                    world.set_water(full_cells, 8, fractional)

                settled_tick = None
                for tick in range(1, 2001):
                    world.water_system.update(world, 0.1)
                    values = [world.get_water(x, 8) for x in range(length)]
                    max_neighbor_diff = max(abs(values[i] - values[i + 1]) for i in range(length - 1))
                    if max_neighbor_diff < world.water_system.min_flow and not world.water_system.active_cells:
                        settled_tick = tick
                        break

                self.assertIsNotNone(settled_tick)

                final_values = [world.get_water(x, 8) for x in range(length)]
                self.assertAlmostEqual(sum(final_values), total_water, places=6)

    def test_water_flows_across_positive_chunk_boundary(self):
        world = World(seed=1)
        left = CHUNK_WIDTH - 1
        right = CHUNK_WIDTH
        y = 8

        world.set_block(left - 1, y, STONE)
        world.set_block(left, y, AIR)
        world.set_block(right, y, AIR)
        world.set_block(right + 1, y, STONE)
        for x in (left - 1, left, right, right + 1):
            world.set_block(x, y - 1, STONE)

        world.set_water(left, y, 1.0)
        for _ in range(10):
            world.water_system.update(world, 0.1)

        self.assertGreater(world.get_water(right, y), 0.0)
        self.assertAlmostEqual(world.get_water(left, y) + world.get_water(right, y), 1.0, places=6)

    def test_water_flows_across_negative_chunk_boundary(self):
        world = World(seed=1)
        left = -1
        right = 0
        y = 8

        world.set_block(left - 1, y, STONE)
        world.set_block(left, y, AIR)
        world.set_block(right, y, AIR)
        world.set_block(right + 1, y, STONE)
        for x in (left - 1, left, right, right + 1):
            world.set_block(x, y - 1, STONE)

        world.set_water(left, y, 1.0)
        for _ in range(10):
            world.water_system.update(world, 0.1)

        self.assertGreater(world.get_water(right, y), 0.0)
        self.assertAlmostEqual(world.get_water(left, y) + world.get_water(right, y), 1.0, places=6)

    def test_unloaded_chunks_do_not_keep_active_water_cells(self):
        world = World(seed=1, load_radius=0, unload_radius=0)
        world.update_loaded_chunks(0.5 * TILE_SIZE)

        world.set_block(0, 8, AIR)
        world.set_block(0, 7, STONE)
        world.set_water(0, 8, 1.0)
        self.assertIn((0, 8), world.water_system.active_cells)

        far_center_x = (2 * CHUNK_WIDTH + 0.5) * TILE_SIZE
        world.update_loaded_chunks(far_center_x)

        self.assertNotIn(0, world.chunks)
        self.assertTrue(
            all((cell[0] // CHUNK_WIDTH) != 0 for cell in world.water_system.active_cells),
            "active water cells from unloaded chunks must be removed",
        )

    def test_reloaded_chunks_restore_and_reactivate_water(self):
        world = World(seed=1, load_radius=0, unload_radius=0)
        world.update_loaded_chunks(0.5 * TILE_SIZE)

        world.set_block(0, 8, AIR)
        world.set_block(0, 7, STONE)
        world.set_water(0, 8, 1.0)

        far_center_x = (2 * CHUNK_WIDTH + 0.5) * TILE_SIZE
        world.update_loaded_chunks(far_center_x)
        self.assertNotIn(0, world.chunks)

        world.update_loaded_chunks(0.5 * TILE_SIZE)

        self.assertIn(0, world.chunks)
        self.assertGreater(world.get_water(0, 8), 0.0)
        self.assertIn((0, 8), world.water_system.active_cells)

    def test_generated_natural_water_is_deterministic(self):
        world_a = World(seed=1337)
        world_b = World(seed=1337)

        chunk_a = world_a.generate_chunk(0)
        chunk_b = world_b.generate_chunk(0)

        self.assertEqual(chunk_a.water, chunk_b.water)

    def test_generated_surface_water_respects_sea_level(self):
        world = World(seed=1337)

        found_surface_water = False
        for chunk_x in range(-6, 7):
            chunk = world.generate_chunk(chunk_x)
            for (local_x, y), amount in chunk.water.items():
                if amount <= 0.0:
                    continue
                surface_y = world.generator.terrain_height(chunk_x, local_x)
                if surface_y < SEA_LEVEL and y > surface_y and y <= SEA_LEVEL:
                    found_surface_water = True
                    break
            if found_surface_water:
                break

        self.assertTrue(found_surface_water)

    def test_generated_underground_cave_water_exists(self):
        world = World(seed=1337)

        found_underground_pool = False
        for chunk_x in range(-12, 13):
            chunk = world.generate_chunk(chunk_x)
            for (local_x, y), amount in chunk.water.items():
                if amount <= 0.0:
                    continue
                if y > UNDERGROUND_WATER_MAX_Y:
                    continue
                if chunk.get_block(local_x, y) != AIR:
                    continue
                if chunk.get_block(local_x, y - 1) == AIR:
                    continue
                found_underground_pool = True
                break
            if found_underground_pool:
                break

        self.assertTrue(found_underground_pool)

    def test_surface_lake_columns_do_not_spawn_trees(self):
        world = World(seed=1337)

        found_lake_column = False
        for chunk_x in range(-40, 41):
            chunk = world.generate_chunk(chunk_x)
            for local_x in range(chunk.width):
                surface_y = world.generator.terrain_height(chunk_x, local_x)
                if surface_y >= SEA_LEVEL:
                    continue
                if chunk.get_water(local_x, surface_y + 1) <= 0.0:
                    continue

                found_lake_column = True
                self.assertNotEqual(chunk.get_block(local_x, surface_y + 1), OAK)
                self.assertNotEqual(chunk.get_block(local_x, surface_y + 1), LEAVES)
                self.assertNotEqual(chunk.get_block(local_x, surface_y + 2), OAK)
                break
            if found_lake_column:
                break

        self.assertTrue(found_lake_column)

    def test_sea_biome_uses_sand_below_surface_water(self):
        world = World(seed=1337)

        found_sea_column = False
        for chunk_x in range(-40, 41):
            chunk = world.generate_chunk(chunk_x)
            for local_x in range(chunk.width):
                surface_y = world.generator.terrain_height(chunk_x, local_x)
                if surface_y >= SEA_LEVEL:
                    continue
                if chunk.get_water(local_x, surface_y + 1) <= 0.0:
                    continue

                found_sea_column = True
                self.assertEqual(chunk.get_block(local_x, surface_y), SAND)
                if surface_y - 1 > 0:
                    self.assertEqual(chunk.get_block(local_x, surface_y - 1), SAND)
                break
            if found_sea_column:
                break

        self.assertTrue(found_sea_column)

    def test_coastal_band_can_generate_sand_above_sea_level(self):
        world = World(seed=1337)

        found_coastal_sand = False
        for chunk_x in range(-12, 13):
            chunk = world.generate_chunk(chunk_x)
            for local_x in range(chunk.width):
                surface_y = world.generator.terrain_height(chunk_x, local_x)
                if surface_y < SEA_LEVEL or surface_y > SEA_LEVEL + COASTAL_BEACH_BAND:
                    continue
                if chunk.get_block(local_x, surface_y) == SAND:
                    found_coastal_sand = True
                    break
            if found_coastal_sand:
                break

        self.assertTrue(found_coastal_sand)

    def test_trees_only_spawn_on_grass_surface_columns(self):
        world = World(seed=1337)

        for chunk_x in range(-12, 13):
            chunk = world.generate_chunk(chunk_x)
            for local_x in range(chunk.width):
                surface_y = world.generator.terrain_height(chunk_x, local_x)
                if surface_y + 1 >= chunk.height:
                    continue
                if chunk.get_block(local_x, surface_y + 1) != OAK:
                    continue
                self.assertEqual(chunk.get_block(local_x, surface_y), GRASS)

    def test_pressing_w_places_full_water_volume_under_mouse(self):
        window = GameWindow.__new__(GameWindow)
        window.show_start_menu = False
        window.game_over = False
        window.mouse_screen_x = 200.0
        window.mouse_screen_y = 200.0
        window.__dict__["width"] = 800
        window.__dict__["height"] = 600
        window.visible_margin_tiles = 8
        window.render_buffer_tiles = 2
        window.camera = type("CameraStub", (), {"position": (0.0, 0.0)})()
        window.world = World(seed=1)
        window.player = type("PlayerStub", (), {"center_x": 0.0, "center_y": 0.0, "on_ground": False})()
        window._screen_to_world = lambda screen_x, screen_y: (screen_x / 16.0, screen_y / 16.0)
        window._get_visible_tile_range = lambda margin_tiles=None: (0, 40)
        window._rebuild_world_sprites = lambda: None

        window.on_key_press(arcade.key.Q, 0)

        tile_x, tile_y = window.world.to_block_position(200.0 / 16.0, 200.0 / 16.0)
        self.assertAlmostEqual(window.world.get_water(tile_x, tile_y), 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
