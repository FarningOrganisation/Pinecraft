import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from load_world_view import LoadWorldView


class _WindowStub:
    def __init__(self):
        self.shown_view = None

    def show_view(self, view):
        self.shown_view = view


class _ServerStub:
    def __init__(self, seed, world_name, initial_save_data=None):
        self.seed = seed
        self.world_name = world_name
        self.initial_save_data = initial_save_data
        self.started = False

    def start(self):
        self.started = True


class LoadWorldViewHostTests(unittest.TestCase):
    def test_selected_save_starts_lan_server_with_save_payload(self):
        view = LoadWorldView.__new__(LoadWorldView)
        view.host_lan = True
        view.window = _WindowStub()
        view.status_label = None
        save_data = {
            "world": {"seed": 42},
            "meta": {"world_name": "Shared World"},
        }
        entry = {"file_name": "SharedWorld.json", "path": "saves/SharedWorld.json"}

        with (
            patch("load_world_view.list_saves", return_value=[entry]),
            patch("load_world_view.load_save", return_value=save_data),
            patch("network.server.LanServer", _ServerStub),
        ):
            with patch("game.GameView", side_effect=lambda **kwargs: kwargs):
                view._on_load("SharedWorld.json")

        shown = view.window.shown_view
        self.assertEqual(shown["seed"], 42)
        self.assertEqual(shown["world_name"], "Shared World")
        self.assertIs(shown["save_data"], save_data)
        self.assertIs(shown["lan_server"].initial_save_data, save_data)
        self.assertTrue(shown["lan_server"].started)

    def test_host_menu_can_open_new_hosted_world_creation(self):
        view = LoadWorldView.__new__(LoadWorldView)
        view.window = _WindowStub()

        with patch("create_world_view.CreateWorldView", side_effect=lambda **kwargs: kwargs):
            view._on_create_hosted_world(None)

        self.assertEqual(view.window.shown_view, {"host_lan": True})


if __name__ == "__main__":
    unittest.main()