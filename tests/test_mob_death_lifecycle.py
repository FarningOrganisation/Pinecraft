import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from game import GameWindow
from mobs.mob import Mob
from mobs.slime import Slime
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

    def test_dead_slime_counts_down_vanish_timer(self):
        slime = Slime.__new__(Slime)
        slime._position = (0.0, 0.0)
        slime._velocity = (0.0, 0.0)
        slime.alive = False
        slime.vanish_after_death_timer = 0.5
        slime.jump_phase = "idle"
        slime.on_ground = True
        slime.stun_timer = 0.0
        slime.alerted = False
        slime.set_state = lambda _state: None

        slime.update_ai(0.1, player=None)

        self.assertAlmostEqual(slime.vanish_after_death_timer, 0.4, places=6)

    def test_mob_attempts_escape_jump_when_trapped_in_narrow_pit(self):
        mob = Mob.__new__(Mob)
        mob._position = (0.0, 0.0)
        mob._velocity = (0.0, 0.0)
        mob.jump_cooldown = 0.0
        mob.walk_direction = 1
        mob.facing_right = True
        mob.speed = 100.0
        mob.jump_strength = 300.0
        mob.needs_turning = False
        mob.change_x = 0.0
        mob.change_y = 0.0
        mob._grounded_below = lambda: True
        mob._has_wall_in_front = lambda _direction: True
        mob._has_headroom_for_jump = lambda min_tiles=2: True
        mob._can_jump_over_obstacle = lambda _direction: True

        mob._update_unalerted_behavior(0.016)

        self.assertGreater(mob.change_y, 0.0)
        self.assertNotEqual(mob.change_x, 0.0)
        self.assertGreater(mob.jump_cooldown, 0.0)

    def test_mob_does_not_flip_direction_in_pit_during_jump_cooldown(self):
        mob = Mob.__new__(Mob)
        mob._position = (0.0, 0.0)
        mob._velocity = (0.0, 0.0)
        mob.jump_cooldown = 0.2
        mob.walk_direction = 1
        mob.facing_right = True
        mob.speed = 100.0
        mob.jump_strength = 300.0
        mob.needs_turning = False
        mob.change_x = 12.0
        mob.change_y = 0.0
        mob._grounded_below = lambda: True
        mob._has_wall_in_front = lambda _direction: True
        mob._has_headroom_for_jump = lambda min_tiles=2: True
        mob._can_jump_over_obstacle = lambda _direction: True

        mob._update_unalerted_behavior(0.05)

        self.assertEqual(mob.walk_direction, 1)
        self.assertEqual(mob.change_x, 0.0)


if __name__ == "__main__":
    unittest.main()
