import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from inventory import InventorySlot
from save_system import build_save_payload


class _DummyMobType:
    pass


class SaveSystemMobSerializationTests(unittest.TestCase):
    def test_build_save_payload_serializes_alive_mobs(self):
        alive_mob = _DummyMobType()
        alive_mob.center_x = 120.0
        alive_mob.center_y = 240.0
        alive_mob.change_x = 12.5
        alive_mob.change_y = -7.0
        alive_mob.health = 2
        alive_mob.max_health = 5
        alive_mob.alive = True
        alive_mob.facing_right = False
        alive_mob.walk_direction = -1
        alive_mob.stun_timer = 0.3
        alive_mob.flee_timer = 0.7
        alive_mob.drop_table = {1029: 0.5, 1030: 0.2}

        dead_mob = _DummyMobType()
        dead_mob.alive = False

        world = type("WorldStub", (), {})()
        world.seed = 42
        world.spawn_x = 10.0
        world.spawn_y = 20.0
        world.saved_chunk_blocks = {}
        world.chunks = {}
        world.saved_chunk_water = {}
        world.saved_chunk_lava = {}
        world.placed_items = {}

        inventory = type("InventoryStub", (), {})()
        inventory.slots = [
            InventorySlot(item=1024, count=1),
            InventorySlot(item=None, count=0),
        ]

        player = type("PlayerStub", (), {})()
        player.inventory = inventory
        player.center_x = 11.0
        player.center_y = 22.0
        player.change_x = 0.0
        player.change_y = 0.0
        player.health = 10
        player.max_health = 10
        player.air_bubbles = 10
        player.max_air_bubbles = 10
        player.selected_hotbar_slot = 0
        player.facing_right = True

        game_view = type("GameViewStub", (), {})()
        game_view.world = world
        game_view.player = player
        game_view.world_name = "TestWorld"
        game_view.time_of_day = 0.5
        game_view.mobs = [alive_mob, dead_mob]

        payload = build_save_payload(game_view)

        self.assertIn("mobs", payload["world"])
        self.assertEqual(len(payload["world"]["mobs"]), 1)

        saved_mob = payload["world"]["mobs"][0]
        self.assertEqual(saved_mob["mob_type"], "_DummyMobType")
        self.assertEqual(saved_mob["position"], {"x": 120.0, "y": 240.0})
        self.assertEqual(saved_mob["velocity"], {"x": 12.5, "y": -7.0})
        self.assertEqual(saved_mob["health"], 2)
        self.assertEqual(saved_mob["max_health"], 5)
        self.assertEqual(saved_mob["facing_right"], False)
        self.assertEqual(saved_mob["walk_direction"], -1)
        self.assertEqual(saved_mob["drop_table"], [[1029, 0.5], [1030, 0.2]])

    def test_build_save_payload_prefers_mob_to_save_data(self):
        world = type("WorldStub", (), {})()
        world.seed = 7
        world.spawn_x = 0.0
        world.spawn_y = 0.0
        world.saved_chunk_blocks = {}
        world.chunks = {}
        world.saved_chunk_water = {}
        world.saved_chunk_lava = {}
        world.placed_items = {}

        inventory = type("InventoryStub", (), {})()
        inventory.slots = [InventorySlot(item=None, count=0)]

        player = type("PlayerStub", (), {})()
        player.inventory = inventory
        player.center_x = 0.0
        player.center_y = 0.0
        player.change_x = 0.0
        player.change_y = 0.0
        player.health = 10
        player.max_health = 10
        player.air_bubbles = 10
        player.max_air_bubbles = 10
        player.selected_hotbar_slot = 0
        player.facing_right = True

        class CustomMob:
            alive = True

            @staticmethod
            def to_save_data() -> dict:
                return {
                    "mob_type": "CustomMob",
                    "current_animation_state": "charging",
                    "custom_state": {"rage": 3},
                }

        game_view = type("GameViewStub", (), {})()
        game_view.world = world
        game_view.player = player
        game_view.world_name = "TestWorld"
        game_view.time_of_day = 0.5
        game_view.mobs = [CustomMob()]

        payload = build_save_payload(game_view)

        self.assertEqual(len(payload["world"]["mobs"]), 1)
        self.assertEqual(
            payload["world"]["mobs"][0],
            {
                "mob_type": "CustomMob",
                "current_animation_state": "charging",
                "custom_state": {"rage": 3},
            },
        )

    def test_build_save_payload_respects_should_save_hook(self):
        world = type("WorldStub", (), {})()
        world.seed = 7
        world.spawn_x = 0.0
        world.spawn_y = 0.0
        world.saved_chunk_blocks = {}
        world.chunks = {}
        world.saved_chunk_water = {}
        world.saved_chunk_lava = {}
        world.placed_items = {}

        inventory = type("InventoryStub", (), {})()
        inventory.slots = [InventorySlot(item=None, count=0)]

        player = type("PlayerStub", (), {})()
        player.inventory = inventory
        player.center_x = 0.0
        player.center_y = 0.0
        player.change_x = 0.0
        player.change_y = 0.0
        player.health = 10
        player.max_health = 10
        player.air_bubbles = 10
        player.max_air_bubbles = 10
        player.selected_hotbar_slot = 0
        player.facing_right = True

        class RitualBoss:
            alive = True

            @staticmethod
            def should_save() -> bool:
                return False

            @staticmethod
            def to_save_data() -> dict:
                return {"mob_type": "RitualBoss"}

        game_view = type("GameViewStub", (), {})()
        game_view.world = world
        game_view.player = player
        game_view.world_name = "TestWorld"
        game_view.time_of_day = 0.5
        game_view.mobs = [RitualBoss()]

        payload = build_save_payload(game_view)
        self.assertEqual(payload["world"]["mobs"], [])


if __name__ == "__main__":
    unittest.main()
