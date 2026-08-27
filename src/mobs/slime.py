"""Slime enemy implementation."""

from __future__ import annotations

import math

import arcade
from paths import textures_dir
from resource_manager import resource_manager

from mobs.monster import Monster
from sprite_animation import SpriteAnimation


class Slime(Monster):
    """A simple jumping slime that chases the player."""
    # TODO_STUDENT (⭐⭐⭐): BabySlime einfuehren und beim Tod grosser Slimes spawnen.

    def __init__(self, world, x: float, y: float, health: int = 3):
        enemy_texture_dir = textures_dir("mobs")
        idle_texture = resource_manager.load_texture(enemy_texture_dir / "slimeBlue.png")
        move_texture = resource_manager.load_texture(enemy_texture_dir / "slimeBlue_move.png")

        animations = {
            "idle": SpriteAnimation([idle_texture, move_texture], fps=1.5, loop=True),
            "move": SpriteAnimation([idle_texture, move_texture], fps=6.0, loop=True),
        }
        super().__init__(
            world,
            x=x,
            y=y,
            health=health,
            activate_range=260.0,
            attack_range=32.0,
            speed=80.0,
            damage=1,
            animations=animations,
            default_state="idle"
        )
        self.jump_speed = 370.0
        self.jump_cooldown = 0.4

        self.texture = self.current_animation.texture
        self.scale = 0.65
        self.collision_width = self.width * 0.45
        self.collision_height = self.height

    def move_toward_player(self, player, delta_time: float, *, speed: float | None = None):
        """Slime-specific movement with a jump arc toward the player."""
        if player is None:
            return

        direction = self.player_direction(player)
        self.facing_right = direction >= 0

        if self.on_ground and self.jump_cooldown <= 0.0:
            wobble = 1.0 + 0.08 * math.sin(self.center_x * 0.07)
            self.change_x = direction * self.speed * 1.15
            self.change_y = self.jump_speed * wobble
            self.on_ground = False
            self.jump_cooldown = 0.95
            self.set_state("move")
        else:
            self.change_x = direction * self.speed * 0.7

    def update_ai(self, delta_time: float, player):
        """Aggressive slime AI: chase the player when in range; otherwise wander."""
        if not self.alive:
            return

        if self.stun_timer > 0.0:
            self.stun_timer = max(0.0, self.stun_timer - delta_time)

        if self.jump_cooldown > 0.0:
            self.jump_cooldown -= delta_time

        self.on_ground = self.on_ground or self._grounded_below()
        if self.on_ground:
            self.change_y = 0.0

        self.alerted = self._can_see_player(player)
        if self.alerted and self.stun_timer <= 0.0:
            self.move_toward_player(player, delta_time)
            self.set_state("move")
            return

        if self.stun_timer > 0.0:
            self.change_x *= 0.92
            return

        self._update_wander_behavior(delta_time)
        self.set_state("move" if abs(self.change_x) > 0.1 else "idle")
