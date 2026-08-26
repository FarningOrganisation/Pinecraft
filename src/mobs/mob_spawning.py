"""Reusable mob spawn helpers."""

from __future__ import annotations

from typing import TypeVar

from mobs.mob import Mob

MobType = TypeVar("MobType", bound=Mob)


def spawn_mob_at(
    world,
    mob_class: type[MobType],
    mob_list: list[MobType],
    sprite_list,
    *,
    x: float,
    y: float,
    print_debug: bool = True,
    **mob_kwargs,
) -> MobType:
    """Creates a mob at an arbitrary world position and registers it."""
    mob = mob_class(world, x=x, y=y, **mob_kwargs)
    mob_list.append(mob)
    sprite_list.append(mob)

    if print_debug:
        print(f"[mob-spawn] {mob.__class__.__name__} x={x:.1f} y={y:.1f}")

    return mob


def spawn_mob_next_to_player(
    world,
    player,
    mob_class: type[MobType],
    mob_list: list[MobType],
    sprite_list,
    *,
    offset_x: float = 96.0,
    offset_y: float = 32.0,
    print_debug: bool = True,
    **mob_kwargs,
) -> MobType:
    """Creates a mob relative to the player position."""
    spawn_x = player.center_x + offset_x
    spawn_y = player.center_y + offset_y
    mob = spawn_mob_at(
        world,
        mob_class,
        mob_list,
        sprite_list,
        x=spawn_x,
        y=spawn_y,
        print_debug=print_debug,
        **mob_kwargs,
    )
    if print_debug:
        print(f"[mob-spawn] player_dx={spawn_x - player.center_x:.1f}")
    return mob


spawn_enemy_at = spawn_mob_at
spawn_enemy_next_to_player = spawn_mob_next_to_player
Enemy = Mob
