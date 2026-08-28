import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from blocks import AIR, OAK, OAK_PLANKS, STONE, COBBLESTONE
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

    def test_single_cell_pattern_1x1_translates_in_3x3_grid(self):
        recipes = {
            STONE: {
                "pattern": [[COBBLESTONE]],
                "count": 1,
            }
        }
        grid = [
            [AIR, AIR, AIR],
            [AIR, AIR, AIR],
            [AIR, AIR, COBBLESTONE],
        ]

        result_item, _, output_count, offset = find_matching_recipe(grid, recipes)
        self.assertEqual(result_item, STONE)
        self.assertEqual(output_count, 1)
        self.assertEqual(offset, (2, 2))

    def test_horizontal_pattern_1x3_translates_vertically(self):
        recipes = {
            STONE: {
                "pattern": [[COBBLESTONE, COBBLESTONE, COBBLESTONE]],
                "count": 1,
            }
        }
        grid = [
            [AIR, AIR, AIR],
            [COBBLESTONE, COBBLESTONE, COBBLESTONE],
            [AIR, AIR, AIR],
        ]

        result_item, _, _, offset = find_matching_recipe(grid, recipes)
        self.assertEqual(result_item, STONE)
        self.assertEqual(offset, (1, 0))

    def test_vertical_pattern_3x1_translates_horizontally(self):
        recipes = {
            STONE: {
                "pattern": [[COBBLESTONE], [COBBLESTONE], [COBBLESTONE]],
                "count": 1,
            }
        }
        grid = [
            [AIR, COBBLESTONE, AIR],
            [AIR, COBBLESTONE, AIR],
            [AIR, COBBLESTONE, AIR],
        ]

        result_item, _, _, offset = find_matching_recipe(grid, recipes)
        self.assertEqual(result_item, STONE)
        self.assertEqual(offset, (0, 1))



if __name__ == "__main__":
    unittest.main()
