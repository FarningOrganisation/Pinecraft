"""Slime enemy implementation."""

from __future__ import annotations

import math

import arcade

from enemy import Enemy
from enemy_physics import update_enemy_physics
from sprite_animation import SpriteAnimation


class Slime(Enemy):
    """A simple jumping slime that chases the player."""

    def __init__(self, world, x: float, y: float, health: int = 3):
        super().__init__(
            world,
            x=x,
            y=y,
            health=health,
            activate_range=260.0,
            attack_range=32.0,
            speed=80.0,
            damage=1,
        )
        self.jump_speed = 370.0
        self.jump_cooldown = 0.4

        idle_texture = arcade.load_texture("assets/textures/enemies/slimeBlue.png")
        move_texture = arcade.load_texture("assets/textures/enemies/slimeBlue_move.png")

        self.animations = {
            "idle": SpriteAnimation([idle_texture, move_texture], fps=1.5, loop=True),
            "move": SpriteAnimation([idle_texture, move_texture], fps=6.0, loop=True),
        }
        self.current_animation = self.animations["idle"]
        self.texture = self.current_animation.texture
        self.scale = 0.65
        self.collision_width = self.width * 0.45
        self.collision_height = self.height
        self.current_state = "idle"

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
        """Handles slime movement, state changes, and contact damage."""
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
        elif self.stun_timer > 0.0:
            self.change_x *= 0.92
        else:
            self.change_x = 0.0
            self.set_state("idle")

        update_enemy_physics(self, delta_time)

        self.handle_contact_damage(player, delta_time)
        super().update(delta_time)
