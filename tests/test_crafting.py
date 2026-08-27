import unittest

from blocks import AIR, OAK, OAK_PLANKS, STONE
from crafting_recipes import CRAFTING_RECIPES
from crafting import find_matching_recipe
from items import STICK



class CraftingDetectionTests(unittest.TestCase):
    def test_single_item_pattern_matches_any_position(self):
        grid = [
            [AIR, AIR, AIR],
            [AIR, OAK, AIR],
            [AIR, AIR, AIR],
        ]

        result_item, _, _, _ = find_matching_recipe(grid, CRAFTING_RECIPES)
        self.assertEqual(result_item, OAK_PLANKS)

    def test_vertical_pair_pattern_matches_any_position(self):
        grid = [
            [AIR, AIR, AIR],
            [AIR, OAK_PLANKS, AIR],
            [AIR, OAK_PLANKS, AIR],
        ]

        result_item, _, _, _ = find_matching_recipe(grid, CRAFTING_RECIPES)
        self.assertEqual(result_item, STICK)



if __name__ == "__main__":
    unittest.main()
