import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from blocks import AIR, OBSIDIAN, STONE
from liquids import LiquidSystem
from lava import MAX_LAVA_UPDATES_PER_TICK
from liquid_interactions import LIQUID_REACTION_THRESHOLD
from water import MAX_WATER_UPDATES_PER_TICK
from world import World
from world_generation import LAVA_RENDER_THRESHOLD, build_chunk_lava_sprite_list, get_lava_render_height


class DummyPlayer:
    def __init__(self, center_x: float, center_y: float, collision_width: float, collision_height: float):
        self.center_x = center_x
        self.center_y = center_y
        self.collision_width = collision_width
        self.collision_height = collision_height
        self.damage_events: list[int] = []

    def take_damage(self, amount: int) -> bool:
        self.damage_events.append(amount)
        return True


class LavaMilestone1Tests(unittest.TestCase):
    def test_lava_storage_is_independent_from_water(self):
        world = World(seed=1)
        world.set_block(0, 8, AIR)

        world.set_water(0, 8, 0.7)
        world.set_lava(0, 8, 1.0)

        self.assertAlmostEqual(world.get_water(0, 8), 0.7, places=6)
        self.assertAlmostEqual(world.get_lava(0, 8), 1.0, places=6)

    def test_lava_updates_on_its_own_tick_timer(self):
        world = World(seed=1)
        world.set_block(0, 9, AIR)
        world.set_block(0, 8, AIR)
        world.set_block(0, 7, AIR)
        world.set_lava(0, 9, 1.0)

        world.update(0.10)
        self.assertAlmostEqual(world.get_lava(0, 9), 1.0, places=6)
        self.assertAlmostEqual(world.get_lava(0, 8), 0.0, places=6)

        world.update(0.11)
        self.assertGreater(world.get_lava(0, 8), 0.0)
        self.assertAlmostEqual(world.get_lava(0, 9), 0.0, places=6)

    def test_water_and_lava_keep_independent_active_state(self):
        world = World(seed=1)
        world.set_block(0, 9, AIR)
        world.set_block(2, 9, AIR)
        world.set_water(0, 9, 1.0)
        world.set_lava(2, 9, 1.0)

        self.assertIsNot(world.water_system.active_cells, world.lava_system.active_cells)
        self.assertIn((0, 9), world.water_system.active_cells)
        self.assertIn((2, 9), world.lava_system.active_cells)

    def test_lava_render_height_uses_threshold_then_eighth_steps(self):
        below = max(0.0, LAVA_RENDER_THRESHOLD - 1e-6)
        at_threshold = LAVA_RENDER_THRESHOLD

        self.assertEqual(get_lava_render_height(below), 0.0)
        self.assertGreater(get_lava_render_height(at_threshold), 0.0)

    def test_chunk_lava_sprites_respect_threshold(self):
        world = World(seed=1)
        world.set_block(0, 8, AIR)

        world.set_lava(0, 8, LAVA_RENDER_THRESHOLD * 0.5)
        sprites = build_chunk_lava_sprite_list(0, world.chunks[0], 0, 20)
        self.assertEqual(len(sprites), 0)

        world.set_lava(0, 8, 1.0)
        sprites = build_chunk_lava_sprite_list(0, world.chunks[0], 0, 20)
        self.assertEqual(len(sprites), 1)

    def test_lava_uses_generic_liquid_update_algorithm(self):
        self.assertIs(World(seed=1).lava_system.__class__.update, LiquidSystem.update)

    def test_lava_falls_when_space_below_is_empty(self):
        world = World(seed=1)
        world.set_block(0, 9, AIR)
        world.set_block(0, 8, AIR)
        world.set_block(0, 7, AIR)
        world.set_lava(0, 9, 1.0)

        world.lava_system.update(world, 0.2)

        self.assertGreater(world.get_lava(0, 8), 0.0)
        self.assertAlmostEqual(world.get_lava(0, 9), 0.0, places=6)

    def test_lava_spreads_horizontally_slower_than_water(self):
        water_world = World(seed=1)
        lava_world = World(seed=1)

        for world in (water_world, lava_world):
            world.set_block(0, 8, AIR)
            world.set_block(1, 8, AIR)
            world.set_block(0, 7, STONE)
            world.set_block(1, 7, STONE)

        water_world.set_water(0, 8, 1.0)
        lava_world.set_lava(0, 8, 1.0)

        water_world.water_system.update(water_world, 0.1)
        lava_world.lava_system.update(lava_world, 0.2)

        self.assertGreater(water_world.get_water(1, 8), lava_world.get_lava(1, 8))

    def test_lava_conservation_in_small_basin(self):
        world = World(seed=1)
        for x in (-2, -1, 0, 1, 2):
            world.set_block(x, 8, AIR)
            world.set_block(x, 7, STONE)
        world.set_block(-2, 8, STONE)
        world.set_block(2, 8, STONE)
        world.set_lava(0, 8, 1.0)

        total_before = sum(world.get_lava(x, 8) for x in (-1, 0, 1))
        for _ in range(30):
            world.lava_system.update(world, 0.2)
        total_after = sum(world.get_lava(x, 8) for x in (-1, 0, 1))

        self.assertAlmostEqual(total_after, total_before, places=6)

    def test_lava_pool_eventually_settles_and_sleeps(self):
        world = World(seed=1)
        for x in range(-1, 7):
            world.set_block(x, 8, AIR)
            world.set_block(x, 7, STONE)
        world.set_block(-1, 8, STONE)
        world.set_block(6, 8, STONE)

        world.set_lava(0, 8, 1.0)
        world.set_lava(1, 8, 1.0)
        world.set_lava(2, 8, 1.0)

        settled_tick = None
        for tick in range(1, 1201):
            world.lava_system.update(world, 0.2)
            values = [world.get_lava(x, 8) for x in range(0, 6)]
            max_neighbor_diff = max(abs(values[i] - values[i + 1]) for i in range(5))
            if max_neighbor_diff < world.lava_system.min_flow and not world.lava_system.active_cells:
                settled_tick = tick
                break

        self.assertIsNotNone(settled_tick)

    def test_large_active_lava_respects_work_budget(self):
        world = World(seed=1)

        for x in range(-450, 451):
            world.set_block(x, 8, AIR)
            world.set_block(x, 7, STONE)
            world.set_lava(x, 8, 1.0)

        world.lava_system.update(world, 0.2)

        processed = int(world.lava_system.debug_last_tick.get("processed_cells", 0))
        self.assertLessEqual(processed, MAX_LAVA_UPDATES_PER_TICK)
        self.assertGreater(len(world.lava_system.active_cells), 0)

    def test_large_stable_lava_eventually_sleeps(self):
        world = World(seed=1)
        length = 24

        for x in range(-1, length + 1):
            world.set_block(x, 8, AIR)
            world.set_block(x, 7, STONE)
        world.set_block(-1, 8, STONE)
        world.set_block(length, 8, STONE)

        total_lava = length * 0.5
        full_cells = int(total_lava)
        fractional = total_lava - full_cells
        for x in range(full_cells):
            world.set_lava(x, 8, 1.0)
        if fractional > 0.0:
            world.set_lava(full_cells, 8, fractional)

        settled_tick = None
        for tick in range(1, 2601):
            world.lava_system.update(world, 0.2)
            values = [world.get_lava(x, 8) for x in range(length)]
            max_neighbor_diff = max(abs(values[i] - values[i + 1]) for i in range(length - 1))
            if max_neighbor_diff < world.lava_system.min_flow and not world.lava_system.active_cells:
                settled_tick = tick
                break

        self.assertIsNotNone(settled_tick)
        final_values = [world.get_lava(x, 8) for x in range(length)]
        self.assertAlmostEqual(sum(final_values), total_lava, places=6)

    def test_water_and_lava_keep_independent_work_budgets(self):
        world = World(seed=1)

        for x in range(-700, 701):
            world.set_block(x, 8, AIR)
            world.set_block(x, 7, STONE)
            world.set_water(x, 8, 1.0)
            world.set_lava(x, 8, 1.0)

        world.water_system.update(world, 0.1)
        world.lava_system.update(world, 0.2)

        water_processed = int(world.water_system.debug_last_tick.get("processed_cells", 0))
        lava_processed = int(world.lava_system.debug_last_tick.get("processed_cells", 0))
        self.assertLessEqual(water_processed, MAX_WATER_UPDATES_PER_TICK)
        self.assertLessEqual(lava_processed, MAX_LAVA_UPDATES_PER_TICK)
        self.assertNotEqual(MAX_WATER_UPDATES_PER_TICK, MAX_LAVA_UPDATES_PER_TICK)

    def test_breaking_block_under_stable_lava_wakes_and_drains(self):
        world = World(seed=1)
        for x in (-2, -1, 0, 1, 2):
            world.set_block(x, 8, AIR)
            world.set_block(x, 7, STONE)
        world.set_block(-2, 8, STONE)
        world.set_block(2, 8, STONE)
        world.set_lava(-1, 8, 0.5)
        world.set_lava(0, 8, 0.5)
        world.set_lava(1, 8, 0.5)

        for _ in range(120):
            world.lava_system.update(world, 0.2)
            if not world.lava_system.active_cells:
                break
        self.assertEqual(world.lava_system.active_cells, set())

        world.break_block(0, 7)

        self.assertIn((0, 8), world.lava_system.active_cells)

        flowed_down = False
        for _ in range(60):
            world.lava_system.update(world, 0.2)
            if world.get_lava(0, 7) > 0.0:
                flowed_down = True
                break

        self.assertTrue(flowed_down)

    def test_placing_block_next_to_stable_lava_wakes_neighbors(self):
        world = World(seed=1)
        for x in (-2, -1, 0, 1, 2):
            world.set_block(x, 8, AIR)
            world.set_block(x, 7, STONE)
        world.set_block(-2, 8, STONE)
        world.set_block(2, 8, STONE)
        world.set_lava(-1, 8, 0.5)
        world.set_lava(0, 8, 0.5)
        world.set_lava(1, 8, 0.5)

        for _ in range(120):
            world.lava_system.update(world, 0.2)
            if not world.lava_system.active_cells:
                break
        self.assertEqual(world.lava_system.active_cells, set())

        world.set_block(1, 9, STONE)

        self.assertIn((1, 8), world.lava_system.active_cells)

    def test_detects_same_cell_water_lava_contact(self):
        world = World(seed=1)
        world.set_block(0, 8, AIR)
        world.set_water(0, 8, 0.8)
        world.set_lava(0, 8, 0.8)

        world.update(0.0)
        contacts = world.consume_detected_liquid_contacts()

        self.assertTrue(contacts)
        self.assertIn((0, 8), contacts)

    def test_detects_neighbor_water_lava_contact(self):
        world = World(seed=1)
        world.set_block(0, 8, AIR)
        world.set_block(1, 8, AIR)
        world.set_water(0, 8, 0.8)
        world.set_lava(1, 8, 0.8)

        world.update(0.0)
        contacts = world.consume_detected_liquid_contacts()

        self.assertTrue(contacts)
        self.assertTrue((0, 8) in contacts or (1, 8) in contacts)

    def test_ignores_residual_liquid_below_reaction_threshold(self):
        world = World(seed=1)
        world.set_block(0, 8, AIR)
        world.set_block(1, 8, AIR)
        world.set_water(0, 8, LIQUID_REACTION_THRESHOLD * 0.5)
        world.set_lava(1, 8, 0.9)

        world.update(0.0)
        contacts = world.consume_detected_liquid_contacts()

        self.assertEqual(contacts, [])

    def test_contact_turns_lava_into_obsidian_and_consumes_lava(self):
        world = World(seed=1)
        world.set_block(0, 8, AIR)
        world.set_block(1, 8, AIR)
        world.set_water(0, 8, 1.0)
        world.set_lava(1, 8, 1.0)

        world.update(0.0)

        self.assertEqual(world.get_block(1, 8), OBSIDIAN)
        self.assertAlmostEqual(world.get_lava(1, 8), 0.0, places=6)

    def test_reaction_does_not_affect_non_contact_lava(self):
        world = World(seed=1)
        world.set_block(0, 8, AIR)
        world.set_block(1, 8, AIR)
        world.set_block(4, 8, AIR)
        world.set_water(0, 8, 1.0)
        world.set_lava(1, 8, 1.0)
        world.set_lava(4, 8, 1.0)

        world.update(0.0)

        self.assertEqual(world.get_block(1, 8), OBSIDIAN)
        self.assertAlmostEqual(world.get_lava(1, 8), 0.0, places=6)
        self.assertEqual(world.get_block(4, 8), AIR)
        self.assertAlmostEqual(world.get_lava(4, 8), 1.0, places=6)

    def test_reaction_is_not_reapplied_after_first_resolution(self):
        world = World(seed=1)
        world.set_block(0, 8, AIR)
        world.set_block(1, 8, AIR)
        world.set_water(0, 8, 1.0)
        world.set_lava(1, 8, 1.0)

        world.update(0.0)
        first_changes = world.consume_changed_blocks()
        first_obsidian_changes = [change for change in first_changes if change[3] == OBSIDIAN]
        self.assertEqual(len(first_obsidian_changes), 1)

        world.update(0.0)
        second_changes = world.consume_changed_blocks()
        second_obsidian_changes = [change for change in second_changes if change[3] == OBSIDIAN]
        self.assertEqual(len(second_obsidian_changes), 0)

    def test_lava_damage_uses_cooldown(self):
        world = World(seed=1)
        world.set_block(0, 8, AIR)
        world.set_lava(0, 8, 1.0)
        player = DummyPlayer(center_x=8.0, center_y=272.0, collision_width=12.0, collision_height=24.0)

        world.update(0.49, player=player, update_chunks=False)
        self.assertEqual(player.damage_events, [])

        world.update(0.02, player=player, update_chunks=False)
        self.assertEqual(player.damage_events, [2])

    def test_lava_damage_below_threshold_does_not_hurt(self):
        world = World(seed=1)
        world.set_block(0, 8, AIR)
        world.set_lava(0, 8, 0.04)
        player = DummyPlayer(center_x=8.0, center_y=272.0, collision_width=12.0, collision_height=24.0)

        world.update(2.0, player=player, update_chunks=False)

        self.assertEqual(player.damage_events, [])

    def test_lava_damage_timer_resets_after_leaving_lava(self):
        world = World(seed=1)
        world.set_block(0, 8, AIR)
        world.set_lava(0, 8, 1.0)
        player = DummyPlayer(center_x=8.0, center_y=272.0, collision_width=12.0, collision_height=24.0)

        world.update(0.30, player=player, update_chunks=False)
        self.assertEqual(player.damage_events, [])

        player.center_x = 200.0
        world.update(0.10, player=player, update_chunks=False)
        self.assertEqual(player.damage_events, [])

        player.center_x = 8.0
        world.update(0.30, player=player, update_chunks=False)
        self.assertEqual(player.damage_events, [])

        world.update(0.20, player=player, update_chunks=False)
        self.assertEqual(player.damage_events, [2])


if __name__ == "__main__":
    unittest.main()
