"""Physische Item-Drops mit Gravitation und Spieler-Anziehung."""

from __future__ import annotations

import math
import random

from settings import TILE_SIZE


class DroppedItem:
    """Kleine Welt-Entity für einen einzelnes gedropptes Item."""

    DESPAWN_SECONDS = 300.0
    WATER_FLOW_MIN_DELTA = 0.01
    WATER_FLOW_ACCEL_LINEAR = 360.0
    WATER_FLOW_ACCEL_QUADRATIC = 520.0
    WATER_LINEAR_DAMPING = 0.90
    WATER_BUOYANCY_ACCEL = 360.0
    WATER_GRAVITY_FACTOR = 0.18
    WATER_VERTICAL_DAMPING = 0.84
    WATER_SURFACE_STICK_BAND = 2.0
    WATER_SURFACE_FLOAT_OFFSET = 0.35

    def __init__(
        self,
        entry_id: int,
        texture,
        spawn_x: float,
        spawn_y: float,
        initial_vx: float | None = None,
        initial_vy: float | None = None,
        pickup_delay_seconds: float = 0.0,
    ):
        self.entry_id = entry_id
        self.sprite = self._build_sprite(texture, spawn_x, spawn_y)

        self.vx = float(initial_vx) if initial_vx is not None else random.uniform(-80.0, 80.0)
        self.vy = float(initial_vy) if initial_vy is not None else random.uniform(80.0, 160.0)
        self.pickup_delay_remaining = max(0.0, float(pickup_delay_seconds))
        self.age_seconds = 0.0
        self.expired = False

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

    def _liquid_contact(self, world) -> tuple[bool, tuple[int, int, float] | None]:
        """Ermittelt Lava-Kontakt und dominante Wasserzelle mit AABB-Overlap."""
        left = self.sprite.center_x - self._half_w()
        right = self.sprite.center_x + self._half_w()
        bottom = self.sprite.center_y - self._half_h()
        top = self.sprite.center_y + self._half_h()

        min_tile_x = int(math.floor(left / TILE_SIZE))
        max_tile_x = int(math.floor((right - 1e-6) / TILE_SIZE))
        min_tile_y = int(math.floor(bottom / TILE_SIZE))
        max_tile_y = int(math.floor((top - 1e-6) / TILE_SIZE))

        touches_lava = False
        dominant_water: tuple[int, int, float] | None = None
        dominant_overlap = 0.0

        for tile_x in range(min_tile_x, max_tile_x + 1):
            for tile_y in range(min_tile_y, max_tile_y + 1):
                tile_left = tile_x * TILE_SIZE
                tile_right = tile_left + TILE_SIZE
                tile_bottom = tile_y * TILE_SIZE

                lava_amount = max(0.0, min(1.0, float(world.get_lava(tile_x, tile_y))))
                if lava_amount > 0.0:
                    lava_top = tile_bottom + lava_amount * TILE_SIZE
                    overlap_w = max(0.0, min(right, tile_right) - max(left, tile_left))
                    overlap_h = max(0.0, min(top, lava_top) - max(bottom, tile_bottom))
                    if overlap_w > 0.0 and overlap_h > 0.0:
                        touches_lava = True
                        break

                water_amount = max(0.0, min(1.0, float(world.get_water(tile_x, tile_y))))
                if water_amount <= 0.0:
                    continue

                water_top = tile_bottom + water_amount * TILE_SIZE
                overlap_w = max(0.0, min(right, tile_right) - max(left, tile_left))
                overlap_h = max(0.0, min(top, water_top) - max(bottom, tile_bottom))
                overlap_area = overlap_w * overlap_h
                if overlap_area <= 0.0:
                    continue

                if overlap_area > dominant_overlap:
                    dominant_overlap = overlap_area
                    dominant_water = (tile_x, tile_y, water_amount)

            if touches_lava:
                break

        return touches_lava, dominant_water

    def update(self, world, player, delta_time: float, gravity: float, pull_radius: float, pickup_radius: float) -> bool:
        """Aktualisiert Bewegung; True bedeutet: aufgesammelt und entfernen."""
        dt = float(delta_time)
        self.age_seconds += float(delta_time)
        if self.age_seconds >= self.DESPAWN_SECONDS:
            self.expired = True
            return False

        if self.pickup_delay_remaining > 0.0:
            self.pickup_delay_remaining = max(0.0, self.pickup_delay_remaining - dt)

        touches_lava, dominant_water = self._liquid_contact(world)
        if touches_lava:
            self.expired = True
            return False

        dx = player.center_x - self.sprite.center_x
        dy = player.center_y - self.sprite.center_y
        dist = math.hypot(dx, dy)

        if self.pickup_delay_remaining <= 0.0 and 0.0 < dist <= pull_radius:
            # Nahe am Spieler übersteigt der Zug die Schwerkraft, damit das Item nach oben fliegt.
            strength = (gravity * 1.6) * (1.0 - dist / pull_radius)
            self.vx += (dx / dist) * strength * dt
            self.vy += (dy / dist) * strength * dt

        if dominant_water is not None:
            self.vx *= self.WATER_LINEAR_DAMPING
            self.vy *= self.WATER_VERTICAL_DAMPING

            water_tile_x, water_tile_y, water_amount = dominant_water
            water_surface_y = (water_tile_y + water_amount) * TILE_SIZE
            target_center_y = water_surface_y + self._half_h() * self.WATER_SURFACE_FLOAT_OFFSET

            # Unter Wasser gilt reduzierte Gravitation.
            self.vy -= gravity * self.WATER_GRAVITY_FACTOR * dt

            if self.sprite.center_y < target_center_y:
                self.vy += self.WATER_BUOYANCY_ACCEL * dt

            if abs(self.sprite.center_y - target_center_y) <= self.WATER_SURFACE_STICK_BAND:
                self.vy *= 0.65

            left_amount = float(world.get_water(water_tile_x - 1, water_tile_y))
            right_amount = float(world.get_water(water_tile_x + 1, water_tile_y))
            # Wasser fliesst vom hoeheren Pegel zum niedrigeren Pegel.
            # left-right > 0 bedeutet Strom nach rechts.
            flow_delta = left_amount - right_amount
            if abs(flow_delta) >= self.WATER_FLOW_MIN_DELTA:
                diff = abs(flow_delta)
                # Hybridmodell: bei kleinen Deltas reagiert es direkt (linear),
                # bei grossen Deltas zieht es deutlich staerker (quadratisch).
                flow_strength = (
                    self.WATER_FLOW_ACCEL_LINEAR * diff
                    + self.WATER_FLOW_ACCEL_QUADRATIC * diff * diff
                )
                self.vx += math.copysign(flow_strength, flow_delta) * dt
        else:
            self.vy -= gravity * dt

        max_speed = 260.0
        self.vx = max(-max_speed, min(max_speed, self.vx))
        self.vy = max(-max_speed, min(max_speed, self.vy))

        next_x = self.sprite.center_x + self.vx * dt
        if self._collides(world, next_x, self.sprite.center_y):
            self.vx *= -0.25
        else:
            self.sprite.center_x = next_x

        next_y = self.sprite.center_y + self.vy * dt
        if self._collides(world, self.sprite.center_x, next_y):
            if self.vy < 0:
                self.vy = 0.0
                self.vx *= 0.88
            else:
                if dominant_water is not None:
                    self.vy = 0.0
                else:
                    self.vy *= -0.2
        else:
            self.sprite.center_y = next_y

        if self.pickup_delay_remaining <= 0.0 and dist <= pickup_radius:
            return True

        return False
