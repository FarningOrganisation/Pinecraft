"""Reusable enemy spawn helpers."""

from __future__ import annotations

from typing import TypeVar

from enemy import Enemy

EnemyType = TypeVar("EnemyType", bound=Enemy)


def spawn_enemy_at(
    world,
    enemy_class: type[EnemyType],
    enemy_list: list[EnemyType],
    sprite_list,
    *,
    x: float,
    y: float,
    print_debug: bool = True,
    **enemy_kwargs,
) -> EnemyType:
    """Creates an enemy at an arbitrary world position and registers it."""
    enemy = enemy_class(world, x=x, y=y, **enemy_kwargs)
    enemy_list.append(enemy)
    sprite_list.append(enemy)

    if print_debug:
        print(f"[enemy-spawn] {enemy.__class__.__name__} x={x:.1f} y={y:.1f}")

    return enemy


def spawn_enemy_next_to_player(
    world,
    player,
    enemy_class: type[EnemyType],
    enemy_list: list[EnemyType],
    sprite_list,
    *,
    offset_x: float = 96.0,
    offset_y: float = 32.0,
    print_debug: bool = True,
    **enemy_kwargs,
) -> EnemyType:
    """Creates an enemy relative to the player position."""
    spawn_x = player.center_x + offset_x
    spawn_y = player.center_y + offset_y
    enemy = spawn_enemy_at(
        world,
        enemy_class,
        enemy_list,
        sprite_list,
        x=spawn_x,
        y=spawn_y,
        print_debug=print_debug,
        **enemy_kwargs,
    )
    if print_debug:
        print(f"[enemy-spawn] player_dx={spawn_x - player.center_x:.1f}")
    return enemy