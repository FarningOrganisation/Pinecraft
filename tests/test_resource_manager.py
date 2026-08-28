import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from paths import ASSETS_DIR, PROJECT_ROOT
from resource_manager import ResourceManager


class ResourceManagerPathTests(unittest.TestCase):
    def test_load_texture_uses_absolute_asset_path_for_assets_prefix(self):
        manager = ResourceManager()

        with patch("resource_manager.arcade.load_texture", return_value=object()) as mock_load:
            manager.load_texture("assets/textures/mobs/zombi1.png")

        called_path = Path(mock_load.call_args[0][0])
        self.assertTrue(called_path.is_absolute())
        self.assertEqual(called_path, (PROJECT_ROOT / "assets/textures/mobs/zombi1.png").resolve())

    def test_load_texture_uses_absolute_asset_path_for_textures_prefix(self):
        manager = ResourceManager()

        with patch("resource_manager.arcade.load_texture", return_value=object()) as mock_load:
            manager.load_texture("textures/mobs/zombi1.png")

        called_path = Path(mock_load.call_args[0][0])
        self.assertTrue(called_path.is_absolute())
        self.assertEqual(called_path, (ASSETS_DIR / "textures/mobs/zombi1.png").resolve())


if __name__ == "__main__":
    unittest.main()
