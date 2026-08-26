"""Compatibility helpers for shared mob physics."""

from __future__ import annotations


def update_mob_physics(mob, delta_time: float):
    """Applies gravity and block collisions to a single mob."""
    if hasattr(mob, "apply_physics"):
        return mob.apply_physics(delta_time)
    raise AttributeError(f"{type(mob).__name__} does not implement apply_physics()")


update_enemy_physics = update_mob_physics