"""Slime enemy implementation."""

from __future__ import annotations

import arcade
from paths import textures_dir
from ids import CHARCOAL

from mobs.monster import Monster
from sprite_animation import SpriteAnimation


class Slime(Monster):
    """A simple jumping slime that chases the player."""
    # TODO_STUDENT (⭐⭐⭐): BabySlime einfuehren und beim Tod grosser Slimes spawnen.

    def __init__(self, world, x: float, y: float, health: int = 3, drop_table: dict[int, float] | None = None):
        self.jump_speed = 560.0
        self.jump_forward_speed = 165.0
        self.jump_direction = 1
        self.jump_phase = "idle"

        mob_texture_dir = textures_dir("mobs", "slime")
        idle_texture = arcade.load_texture(mob_texture_dir / "Slime1.png")
        prep_textures = [arcade.load_texture(mob_texture_dir / f"Slime{i}.png") for i in range(1, 7)]
        jump_textures = [arcade.load_texture(mob_texture_dir / f"Slime{i}.png") for i in range(7, 13)]

        animations = {
            "idle": SpriteAnimation([idle_texture], fps=1.5, loop=True),
            "prep": SpriteAnimation(prep_textures, fps=14.0, loop=False),
            "jump": SpriteAnimation(jump_textures, fps=14.0, loop=False),
        }
        loot_table = {CHARCOAL: 0.35} if drop_table is None else drop_table
        super().__init__(
            world,
            x=x,
            y=y,
            health=health,
            activate_range=500.0,
            speed=20.0,
            damage=1,
            animations=animations,
            default_state="idle",
            drop_table=loot_table,
        )

        self.scale = 2
        self.collision_width = self.width
        self.collision_height = self.height
        self.current_state = "idle"
        self.jump_cooldown = 0.0

    def _reset_prep_cycle(self):
        """Startet den Kontraktionszyklus wieder bei Slime1."""
        prep_animation = self.animations.get("prep")
        if prep_animation is not None:
            prep_animation.reset()
            self.texture = prep_animation.texture

    def _start_jump(self, direction: int):
        """Launches an aggressive jump toward the current target direction."""
        self.jump_direction = 1 if direction >= 0 else -1
        self.change_x = direction * self.jump_forward_speed
        self.change_y = self.jump_speed
        self.on_ground = False
        self.jump_phase = "air"
        self.set_state("jump")

    def _update_alerted_behavior(self, player, delta_time: float, *, speed: float | None = None):
        """Runs the 1-12 slime jump cycle while chasing the player."""
        if player is None:
            return

        direction = self.player_direction(player)
        self.facing_right = direction >= 0

        if self.jump_phase == "air":
            if self.on_ground:
                self.change_x = 0.0
                self.jump_phase = "pre_jump"
                self.set_state("prep")
                self._reset_prep_cycle()
            else:
                # Horizontalimpuls in der Luft erneut anwenden, falls Kollision ihn auf 0 gesetzt hat.
                self.change_x = self.jump_direction * self.jump_forward_speed
                self.set_state("jump")
            return

        self.change_x = 0.0
        self.jump_phase = "pre_jump"
        self.set_state("prep")

        prep_animation = self.animations.get("prep")
        if prep_animation is not None and prep_animation.has_finished:
            self._start_jump(direction)

    def _update_unalerted_behavior(self, delta_time: float):
        """Slimes do not wander; they either keep their jump arc or stay still."""
        if self.jump_phase == "air" and not self.on_ground:
            self.change_x = self.jump_direction * self.jump_forward_speed
            self.set_state("jump")
            return

        self.change_x = 0.0
        if self.on_ground:
            self.jump_phase = "idle"

    def update_ai(self, delta_time: float, player):
        """Uses shared monster AI flow with slime-specific jump/wander behavior."""
        super().update_ai(delta_time, player)

        if self.jump_phase == "air" and not self.on_ground and self.stun_timer <= 0.0:
            self.set_state("jump")
        elif not self.alerted and self.on_ground:
            self.jump_phase = "idle"
            self.set_state("idle")
