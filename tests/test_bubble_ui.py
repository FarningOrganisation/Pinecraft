import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ui.bubble_ui import BubbleUI


class PlayerStub:
    def __init__(self):
        self.in_water = True
        self.max_air_bubbles = 3
        self.air_bubbles = 3


class HotbarStub:
    pass


class HealthUIStub:
    heart_size = 16

    @staticmethod
    def get_bar_origin():
        return 0, 0


class BubbleUITests(unittest.TestCase):
    def test_pop_texture_is_shown_for_half_second_then_disappears(self):
        player = PlayerStub()
        ui = BubbleUI(player, HotbarStub(), HealthUIStub())

        drawn_textures = []

        def _capture(texture, rect, alpha=255, pixelated=False):
            drawn_textures.append(texture)

        with patch("ui.bubble_ui.arcade.draw_texture_rect", side_effect=_capture):
            with patch("ui.bubble_ui.time.monotonic", return_value=10.0):
                ui.draw()
            self.assertEqual(len(drawn_textures), 3)
            self.assertEqual(drawn_textures.count(ui.bubble_full_texture), 3)

            drawn_textures.clear()
            player.air_bubbles = 2
            with patch("ui.bubble_ui.time.monotonic", return_value=10.1):
                ui.draw()
            self.assertEqual(len(drawn_textures), 3)
            self.assertEqual(drawn_textures.count(ui.bubble_full_texture), 2)
            self.assertEqual(drawn_textures.count(ui.bubble_pop_texture), 1)

            drawn_textures.clear()
            with patch("ui.bubble_ui.time.monotonic", return_value=10.7):
                ui.draw()
            self.assertEqual(len(drawn_textures), 2)
            self.assertEqual(drawn_textures.count(ui.bubble_full_texture), 2)
            self.assertEqual(drawn_textures.count(ui.bubble_pop_texture), 0)


if __name__ == "__main__":
    unittest.main()
