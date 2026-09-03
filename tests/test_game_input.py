import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from game import GameView


class GameInputTests(unittest.TestCase):
    def test_key_press_without_symbol_is_ignored(self):
        view = GameView.__new__(GameView)

        view.on_key_press(None, 0)


if __name__ == "__main__":
    unittest.main()