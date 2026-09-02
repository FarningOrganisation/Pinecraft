"""Template for creating a new hostile monster.

Usage:
1) Copy this file and rename class/file.
2) Register your monster with @register_mob("YourMonsterType").
3) Implement AI hooks (_update_alerted_behavior / _update_attack_behavior).
4) Optionally persist custom fields via save_state/load_state.
"""

from __future__ import annotations

from paths import textures_dir
from sprite_animation import SpriteAnimation

from mobs.monster import Monster
from mobs.registry import register_mob


@register_mob("MyMonster")
class MyMonster(Monster):
    """Hostile monster template.

    This class already plugs into:
    - Mob registry (automatic save/load type resolution)
    - Monster chase/contact-damage flow
    - Base serialization (position, velocity, health, current_animation_state, etc.)
    """

    def __init__(self, world, x: float, y: float, drop_table: dict[int, float] | None = None):
        # 1) Define textures/animations for your monster.
        texture_dir = textures_dir("mobs", "my_monster")
        animations = {
            "idle": SpriteAnimation([texture_dir / "idle.png"], fps=4.0, loop=True),
            "walking": SpriteAnimation([texture_dir / "walk_1.png", texture_dir / "walk_2.png"], fps=10.0, loop=True),
            "attack": SpriteAnimation([texture_dir / "attack_1.png", texture_dir / "attack_2.png"], fps=14.0, loop=False),
        }

        # 2) Optional default loot table.
        loot_table = {} if drop_table is None else drop_table

        # 3) Call Monster constructor with tuning parameters.
        super().__init__(
            world,
            x=x,
            y=y,
            animations=animations,
            default_state="idle",
            health=6,
            activate_range=420.0,
            aggro_duration=2.5,
            attack_range=34.0,
            speed=120.0,
            damage=2,
            drop_table=loot_table,
        )

        # 4) Add custom runtime fields.
        self.attack_cooldown = 0.0

    def _update_alerted_behavior(self, player, delta_time: float, *, speed: float | None = None):
        """Optional: customize chase/pathing while alert.

        You can keep base behavior by calling super().
        """
        super()._update_alerted_behavior(player, delta_time, speed=speed)

    def _update_attack_behavior(self, player, delta_time: float):
        """Optional: custom attack logic when player is in range.

        Contact damage is already handled by Monster.update().
        Implement extra attacks (projectiles, windups, AoE) here.
        """
        self.attack_cooldown = max(0.0, self.attack_cooldown - delta_time)
        if self.attack_cooldown <= 0.0:
            self.set_animation_state("attack")
            # Example: trigger ability/projectile here.
            self.attack_cooldown = 1.2

    def save_state(self) -> dict:
        """Persist only custom fields not already covered by base classes."""
        return {
            "attack_cooldown": float(self.attack_cooldown),
        }

    def load_state(self, state: dict) -> None:
        """Restore custom fields saved by save_state()."""
        try:
            self.attack_cooldown = max(0.0, float(state.get("attack_cooldown", 0.0)))
        except (TypeError, ValueError):
            self.attack_cooldown = 0.0
