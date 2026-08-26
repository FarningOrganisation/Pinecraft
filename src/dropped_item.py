"""Physische Item-Drops mit Gravitation und Spieler-Anziehung."""

from __future__ import annotations

import math
import random

from settings import TILE_SIZE


class DroppedItem:
    """Kleine Welt-Entity für einen einzelnes gedropptes Item."""

    def __init__(self, entry_id: int, texture, spawn_x: float, spawn_y: float):
        self.entry_id = entry_id
        self.sprite = self._build_sprite(texture, spawn_x, spawn_y)

        self.vx = random.uniform(-80.0, 80.0)
        self.vy = random.uniform(80.0, 160.0)

    @staticmethod
    def _build_sprite(texture, spawn_x: float, spawn_y: float):
        import arcade

        sprite = arcade.Sprite(texture)
        sprite.center_x = spawn_x
        sprite.center_y = spawn_y
        sprite.width = TILE_SIZE * 0.6
        sprite.height = TILE_SIZE * 0.6
        return sprite

    def _half_w(self) -> float:
        return self.sprite.width / 2

    def _half_h(self) -> float:
        return self.sprite.height / 2

    def _collides(self, world, x: float, y: float) -> bool:
        left = x - self._half_w()
        right = x + self._half_w()
        bottom = y - self._half_h()
        top = y + self._half_h()

        for _tile_x, _tile_y, block_left, block_right, block_bottom, block_top in world.get_blocks_around(
            left, right, bottom, top
        ):
            if right <= block_left or left >= block_right:
                continue
            if top <= block_bottom or bottom >= block_top:
                continue
            return True
        return False

    def update(self, world, player, delta_time: float, gravity: float, pull_radius: float, pickup_radius: float) -> bool:
        """Aktualisiert Bewegung; True bedeutet: aufgesammelt und entfernen."""
        dx = player.center_x - self.sprite.center_x
        dy = player.center_y - self.sprite.center_y
        dist = math.hypot(dx, dy)

        if 0.0 < dist <= pull_radius:
            # Nahe am Spieler übersteigt der Zug die Schwerkraft, damit das Item nach oben fliegt.
            strength = (gravity * 1.6) * (1.0 - dist / pull_radius)
            self.vx += (dx / dist) * strength * delta_time
            self.vy += (dy / dist) * strength * delta_time

        self.vy -= gravity * delta_time

        max_speed = 260.0
        self.vx = max(-max_speed, min(max_speed, self.vx))
        self.vy = max(-max_speed, min(max_speed, self.vy))

        next_x = self.sprite.center_x + self.vx * delta_time
        if self._collides(world, next_x, self.sprite.center_y):
            self.vx *= -0.25
        else:
            self.sprite.center_x = next_x

        next_y = self.sprite.center_y + self.vy * delta_time
        if self._collides(world, self.sprite.center_x, next_y):
            if self.vy < 0:
                self.vy = 0.0
                self.vx *= 0.88
            else:
                self.vy *= -0.2
        else:
            self.sprite.center_y = next_y

        if dist <= pickup_radius:
            return True

        return False
