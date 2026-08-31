import sys
import unittest
from pathlib import Path

import arcade

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from blocks import COBBLESTONE, COBBLESTONE_BG, STONE, OAK_PLANKS, OAK, BLOCKS, get_foreground_block_id
from inventory import Inventory
from ui.inventory_ui import InventoryUI


class PlayerStub:
    def __init__(self):
        self.inventory = Inventory()
        self.selected_hotbar_slot = 0


class InventoryUIOffsetTests(unittest.TestCase):
    def test_non_solid_background_texture_and_solid_partner_texture(self):
        self.assertTrue(BLOCKS[OAK]["texture"].startswith("background/"))

        oak_solid_id = get_foreground_block_id(OAK)
        self.assertIsNotNone(oak_solid_id)
        self.assertEqual(BLOCKS[oak_solid_id]["texture"], "oak.png")
        self.assertTrue(BLOCKS[oak_solid_id]["solid"])

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

    def test_conversion_output_click_converts_one_item(self):
        player = PlayerStub()
        ui = InventoryUI(player, screen_width=1200, screen_height=420)
        ui.visible = True

        ui.conversion_input_slot.item = COBBLESTONE
        ui.conversion_input_slot.count = 2

        output_rect = ui._conversion_output_slot_rect()
        handled = ui.handle_click(output_rect.center_x, output_rect.center_y, arcade.MOUSE_BUTTON_LEFT, 0)

        self.assertTrue(handled)
        self.assertEqual(ui.conversion_input_slot.item, COBBLESTONE)
        self.assertEqual(ui.conversion_input_slot.count, 1)
        self.assertEqual(player.inventory.get_item_count(COBBLESTONE_BG), 1)

    def test_bin_overwrite_and_take_back(self):
        player = PlayerStub()
        ui = InventoryUI(player, screen_width=1200, screen_height=420)
        ui.visible = True

        hotbar_index = player.inventory.HOTBAR_START + player.selected_hotbar_slot
        selected_slot = player.inventory.get_slot(hotbar_index)

        selected_slot.item = STONE
        selected_slot.count = 3

        bin_rect = ui._bin_slot_rect()
        handled = ui.handle_click(bin_rect.center_x, bin_rect.center_y, arcade.MOUSE_BUTTON_LEFT, 0)
        self.assertTrue(handled)
        self.assertEqual(ui.bin_slot.item, STONE)
        self.assertEqual(ui.bin_slot.count, 3)
        self.assertEqual(selected_slot.item, None)
        self.assertEqual(selected_slot.count, 0)

        selected_slot.item = OAK_PLANKS
        selected_slot.count = 2
        handled = ui.handle_click(bin_rect.center_x, bin_rect.center_y, arcade.MOUSE_BUTTON_LEFT, 0)
        self.assertTrue(handled)
        self.assertEqual(ui.bin_slot.item, OAK_PLANKS)
        self.assertEqual(ui.bin_slot.count, 2)

        selected_slot.item = None
        selected_slot.count = 0
        handled = ui.handle_click(bin_rect.center_x, bin_rect.center_y, arcade.MOUSE_BUTTON_LEFT, 0)
        self.assertTrue(handled)
        self.assertEqual(selected_slot.item, OAK_PLANKS)
        self.assertEqual(selected_slot.count, 2)
        self.assertEqual(ui.bin_slot.item, None)
        self.assertEqual(ui.bin_slot.count, 0)


if __name__ == "__main__":
    unittest.main()
