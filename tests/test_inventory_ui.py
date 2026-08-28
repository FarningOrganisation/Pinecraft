import sys
import unittest
from pathlib import Path

import arcade

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from blocks import STONE
from inventory import Inventory
from ui.inventory_ui import InventoryUI


class PlayerStub:
    def __init__(self):
        self.inventory = Inventory()
        self.selected_hotbar_slot = 0


class InventoryUIOffsetTests(unittest.TestCase):
    def test_result_click_consumes_materials_with_recipe_offset(self):
        player = PlayerStub()
        ui = InventoryUI(player, screen_width=1200, screen_height=420)
        ui.visible = True

        # Place one required item into center slot (row 1, col 1 => index 4).
        ui.crafting_slots[4].item = STONE
        ui.crafting_slots[4].count = 1

        pattern = [
            [STONE, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
        ]

        ui._find_matching_recipe = lambda: (STONE, pattern, 1, (1, 1))

        result_rect = ui._result_slot_rect()
        click_x = result_rect.center_x
        click_y = result_rect.center_y

        handled = ui.handle_click(click_x, click_y, arcade.MOUSE_BUTTON_LEFT, 0)

        self.assertTrue(handled)
        self.assertEqual(ui.crafting_slots[4].item, None)
        self.assertEqual(ui.crafting_slots[4].count, 0)


if __name__ == "__main__":
    unittest.main()
