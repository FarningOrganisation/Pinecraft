import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from game import GameWindow
from mobs.zombie import Zombie


class FakeMob:
    def __init__(self, alive: bool, vanish_after_death_timer: float):
        self.alive = alive
        self.vanish_after_death_timer = vanish_after_death_timer
        self.center_y = 10.0

    def update(self, delta_time, player):
        if not self.alive:
            self.vanish_after_death_timer -= delta_time


class FakeSpriteList:
    def __init__(self, items=None):
        self.items = list(items or [])

    def remove(self, mob):
        self.items.remove(mob)


class MobDeathLifecycleTests(unittest.TestCase):
    def test_dead_mob_is_removed_after_death_timer_expires(self):
        window = GameWindow.__new__(GameWindow)
        mob = FakeMob(alive=False, vanish_after_death_timer=0.0)
        window.mobs = [mob]
        window.mob_sprite_list = FakeSpriteList([mob])
        window.player = object()
        window._spawn_mob_if_needed = lambda: None
        window.mob_spawn_timer = 0.0

        window._update_mobs(0.1)

        self.assertEqual(window.mobs, [])
        self.assertEqual(window.mob_sprite_list.items, [])

    def test_mob_damage_flash_is_set_on_take_damage(self):
        mob = FakeMob(alive=True, vanish_after_death_timer=0.5)
        mob.take_damage = lambda amount: setattr(mob, "damage_flash_timer", 0.15) or None

        mob.take_damage(1)

        self.assertGreater(mob.damage_flash_timer, 0.0)

    def test_night_spawn_pool_includes_zombies(self):
        window = GameWindow.__new__(GameWindow)
        window.mobs = []
        window.max_active_mobs = 10
        window.mob_spawn_timer = 0.0
        window.player = type("PlayerStub", (), {"center_x": 0.0, "center_y": 0.0})()
        window.world = type("WorldStub", (), {"get_ground_top": lambda self, x: 0.0})()
        window._day_factor = lambda: 0.0
        window._can_spawn_mob_at = lambda *args, **kwargs: True

        spawned_classes = []

        def fake_spawn_mob(mob_class, x, y, **kwargs):
            spawned_classes.append(mob_class)
            return object()

        window.spawn_mob = fake_spawn_mob
        original_choice = random.choice
        random.choice = lambda seq: seq[1]
        try:
            window._spawn_mob_if_needed()
        finally:
            random.choice = original_choice

        self.assertIn(Zombie, spawned_classes)


if __name__ == "__main__":
    unittest.main()
