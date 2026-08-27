"""Lokale AABB-Physik für den Spieler in Pinecraft.

Die Physik prüft nur die Blöcke in der Nähe des Spielers und nicht die
komplette Welt. So bleiben die Berechnungen klein, verständlich und robust.
"""

from __future__ import annotations

import math

from blocks import AIR, is_block_solid
from settings import GRAVITY, TILE_SIZE


def aabb_from_center(center_x: float, center_y: float, width: float, height: float) -> tuple[float, float, float, float]:
    """Builds an axis-aligned box from center coordinates and dimensions."""
    half_w = width / 2.0
    half_h = height / 2.0
    return center_x - half_w, center_x + half_w, center_y - half_h, center_y + half_h


def aabb_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    """Returns True when two AABBs intersect."""
    a_left, a_right, a_bottom, a_top = a
    b_left, b_right, b_bottom, b_top = b
    return a_left < b_right and a_right > b_left and a_bottom < b_top and a_top > b_bottom


class AABBPhysics:
    """Einfache, lokale Kollision und Gravitation für einen Spieler."""

    def __init__(self, world):
        self.world = world
        # Kleine Toleranz verhindert sporadisches Hängenbleiben
        # in exakt 2-Block-hohen Gängen durch Float-Ungenauigkeiten.
        self.collision_skin = 0.35

    def _box_left(self, player):
        return player.center_x - player.collision_width / 2

    def _box_right(self, player):
        return player.center_x + player.collision_width / 2

    def _box_bottom(self, player):
        return player.center_y - player.collision_height / 2

    def _box_top(self, player):
        return player.center_y + player.collision_height / 2

    def _grounded_below_player(self, player) -> bool:
        """Prüft, ob direkt unter dem Spieler ein Block liegt."""
        left = self._box_left(player) + 2
        right = self._box_right(player) - 2
        probe_y = self._box_bottom(player) - 1.0
        min_tile_x = int(math.floor(left / TILE_SIZE))
        max_tile_x = int(math.floor(right / TILE_SIZE))
        ground_tile_y = int(math.floor(probe_y / TILE_SIZE))

        for tile_x in range(min_tile_x, max_tile_x + 1):
            block_id = self.world.get_block(tile_x, ground_tile_y, generate_if_missing=False)
            if block_id != AIR and is_block_solid(block_id):
                return True
        return False

    def _resolve_horizontal(self, player, previous_left, previous_right):
        """Behandelt seitliche Kollisionen mit Blöcken."""
        left = self._box_left(player)
        right = self._box_right(player)
        bottom = self._box_bottom(player)
        top = self._box_top(player)
        skin = self.collision_skin

        for tile_x, tile_y, block_x_min, block_x_max, block_y_min, block_y_max in self.world.get_blocks_around(
            left, right, bottom, top
        ):
            if not (bottom + skin < block_y_max and top - skin > block_y_min):
                continue

            is_jump_impulse = player.change_y > 0.0

            if player.change_x > 0 and previous_right <= block_x_min:
                player.center_x = block_x_min - player.collision_width / 2 - skin
                if not is_jump_impulse:
                    player.change_x = 0.0
            elif player.change_x < 0 and previous_left >= block_x_max:
                player.center_x = block_x_max + player.collision_width / 2 + skin
                if not is_jump_impulse:
                    player.change_x = 0.0

    def _resolve_vertical(self, player, previous_bottom, previous_top):
        """Behandelt Kollisionen von oben und unten mit Blöcken."""
        left = self._box_left(player)
        right = self._box_right(player)
        bottom = self._box_bottom(player)
        top = self._box_top(player)
        skin = self.collision_skin

        for tile_x, tile_y, block_x_min, block_x_max, block_y_min, block_y_max in self.world.get_blocks_around(
            left, right, bottom, top
        ):
            if not (left + skin < block_x_max and right - skin > block_x_min):
                continue

            if player.change_y > 0 and previous_top <= block_y_min:
                player.center_y = block_y_min - player.collision_height / 2 - skin
                player.change_y = 0.0
            elif player.change_y < 0 and previous_bottom >= block_y_max:
                player.center_y = block_y_max + player.collision_height / 2 + skin
                player.change_y = 0.0
                player.on_ground = True

    def update(self, player, delta_time: float):
        """Bewegt den Spieler mit Gravitation, seitlichen Kollisionen und Bodenprüfung."""
        previous_left = self._box_left(player)
        previous_right = self._box_right(player)
        previous_bottom = self._box_bottom(player)
        previous_top = self._box_top(player)

        player.on_ground = self._grounded_below_player(player)
        if not player.on_ground:
            gravity_multiplier = 1.0
            if hasattr(player, "get_gravity_multiplier"):
                gravity_multiplier = max(0.0, float(player.get_gravity_multiplier()))
            player.change_y -= GRAVITY * gravity_multiplier * delta_time

        player.center_x += player.change_x * delta_time
        self._resolve_horizontal(player, previous_left, previous_right)

        player.center_y += player.change_y * delta_time
        player.on_ground = False
        self._resolve_vertical(player, previous_bottom, previous_top)

        if self._grounded_below_player(player):
            player.on_ground = True
            player.change_y = 0.0

        self._update_falling_sand_stub()

        return player.on_ground

    def _update_falling_sand_stub(self):
        """Hook für fallenden Sand als Schüleraufgabe."""
        # TODO_STUDENT (⭐⭐):
        # - Suche Sandblöcke mit Luft darunter
        # - Lass sie pro Tick nach unten rutschen
        # - Starte klein: nur nahe am Spieler prüfen
        return
