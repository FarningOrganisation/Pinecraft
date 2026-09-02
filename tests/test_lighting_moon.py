import sys
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from blocks import AIR, STONE
from lighting import LightingSystem
from settings import CHUNK_WIDTH, TILE_SIZE, WORLD_HEIGHT
from world import World


class LightingMoonOcclusionTests(unittest.TestCase):
    def _make_flat_air_world(self) -> World:
        world = World(seed=1, load_radius=0, unload_radius=0)
        world.update_loaded_chunks(0.5 * TILE_SIZE)
        chunk = world.chunks[0]
        for y in range(WORLD_HEIGHT):
            for local_x in range(CHUNK_WIDTH):
                chunk.set_block(local_x, y, AIR)
        return world

    def _make_lighting_stub(self, world: World, player_tile_x: int, player_tile_y: int) -> LightingSystem:
        lighting = LightingSystem.__new__(LightingSystem)
        width = 800
        height = 600
        lighting.window = SimpleNamespace(
            world=world,
            width=width,
            height=height,
            time_of_day=0.0,
            camera=SimpleNamespace(position=(0.0, 0.0)),
            player=SimpleNamespace(
                center_x=(player_tile_x + 0.5) * TILE_SIZE,
                center_y=(player_tile_y + 0.5) * TILE_SIZE,
            ),
        )
        lighting._can_player_see_celestials = lambda: True
        lighting.day_factor = lambda: 0.0
        moon_world_x = 8.5 * TILE_SIZE
        moon_world_y = 8.5 * TILE_SIZE
        lighting._moon_screen_position = lambda: (
            (width * 0.5) + moon_world_x,
            (height * 0.5) + moon_world_y,
        )
        return lighting

    def test_moon_light_disabled_when_occluded(self):
        world = self._make_flat_air_world()
        world.set_block(4, 4, STONE)
        lighting = self._make_lighting_stub(world, player_tile_x=0, player_tile_y=0)

        moon_light = lighting._moon_world_light()

        self.assertIsNone(moon_light)

    def test_moon_light_enabled_with_clear_line_of_sight(self):
        world = self._make_flat_air_world()
        lighting = self._make_lighting_stub(world, player_tile_x=0, player_tile_y=0)

        moon_light = lighting._moon_world_light()

        self.assertIsNotNone(moon_light)

    def test_moon_texture_draw_is_not_ambient_tinted(self):
        world = self._make_flat_air_world()
        lighting = self._make_lighting_stub(world, player_tile_x=0, player_tile_y=0)

        sprite = SimpleNamespace(center_x=0.0, center_y=0.0, color=(0, 0, 0), alpha=0)
        lighting.moon_sprite = sprite
        lighting.ambient_color = lambda: (32, 48, 72)
        lighting._moon_screen_position = lambda: (321.0, 654.0)

        with patch("lighting.arcade.draw_sprite", lambda _sprite: None):
            lighting.draw_moon_no_ambient()

        self.assertEqual(sprite.color, (255, 255, 255))
        self.assertEqual(sprite.alpha, 255)
        self.assertEqual(sprite.center_x, 321.0)
        self.assertEqual(sprite.center_y, 654.0)


if __name__ == "__main__":
    unittest.main()