"""Shared enemy physics helpers."""

from __future__ import annotations

import math

from blocks import AIR, is_block_solid
from settings import GRAVITY, TILE_SIZE


def _box_left(enemy):
    return enemy.center_x - enemy.collision_width / 2


def _box_right(enemy):
    return enemy.center_x + enemy.collision_width / 2


def _box_bottom(enemy):
    return enemy.center_y - enemy.collision_height / 2


def _box_top(enemy):
    return enemy.center_y + enemy.collision_height / 2


def _grounded_below(enemy) -> bool:
    world = enemy.world
    if world is None:
        return False

    left = _box_left(enemy) + 2.0
    right = _box_right(enemy) - 2.0
    probe_y = _box_bottom(enemy) - 1.0
    min_tile_x = int(math.floor(left / TILE_SIZE))
    max_tile_x = int(math.floor(right / TILE_SIZE))
    ground_tile_y = int(math.floor(probe_y / TILE_SIZE))

    for tile_x in range(min_tile_x, max_tile_x + 1):
        block_id = world.get_block(tile_x, ground_tile_y, generate_if_missing=False)
        if block_id != AIR and is_block_solid(block_id):
            return True
    return False


def _resolve_horizontal(enemy, previous_left: float, previous_right: float):
    world = enemy.world
    if world is None:
        return

    left = _box_left(enemy)
    right = _box_right(enemy)
    bottom = _box_bottom(enemy)
    top = _box_top(enemy)
    skin = 0.25

    for _, _, block_x_min, block_x_max, block_y_min, block_y_max in world.get_blocks_around(left, right, bottom, top):
        if not (bottom + skin < block_y_max and top - skin > block_y_min):
            continue

        if enemy.change_x > 0 and previous_right <= block_x_min:
            enemy.center_x = block_x_min - enemy.collision_width / 2 - skin
            enemy.change_x = 0.0
        elif enemy.change_x < 0 and previous_left >= block_x_max:
            enemy.center_x = block_x_max + enemy.collision_width / 2 + skin
            enemy.change_x = 0.0


def _resolve_vertical(enemy, previous_bottom: float, previous_top: float):
    world = enemy.world
    if world is None:
        return

    left = _box_left(enemy)
    right = _box_right(enemy)
    bottom = _box_bottom(enemy)
    top = _box_top(enemy)
    skin = 0.25

    for _, _, block_x_min, block_x_max, block_y_min, block_y_max in world.get_blocks_around(left, right, bottom, top):
        if not (left + skin < block_x_max and right - skin > block_x_min):
            continue

        if enemy.change_y > 0 and previous_top <= block_y_min:
            enemy.center_y = block_y_min - enemy.collision_height / 2 - skin
            enemy.change_y = 0.0
        elif enemy.change_y < 0 and previous_bottom >= block_y_max:
            enemy.center_y = block_y_max + enemy.collision_height / 2 + skin
            enemy.change_y = 0.0
            enemy.on_ground = True


def update_enemy_physics(enemy, delta_time: float):
    """Applies gravity and block collisions to a single enemy."""
    previous_left = _box_left(enemy)
    previous_right = _box_right(enemy)
    previous_bottom = _box_bottom(enemy)
    previous_top = _box_top(enemy)

    was_grounded = _grounded_below(enemy)
    enemy.on_ground = was_grounded

    if not was_grounded or enemy.change_y > 0.0:
        enemy.change_y -= GRAVITY * delta_time
    elif enemy.change_y < 0.0:
        enemy.change_y = 0.0

    enemy.center_x += enemy.change_x * delta_time
    _resolve_horizontal(enemy, previous_left, previous_right)

    enemy.center_y += enemy.change_y * delta_time
    enemy.on_ground = False
    _resolve_vertical(enemy, previous_bottom, previous_top)

    if _grounded_below(enemy):
        enemy.on_ground = True
        if enemy.change_y < 0.0:
            enemy.change_y = 0.0

    return enemy.on_ground