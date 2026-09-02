"""Template for creating a new neutral mob.

Usage:
1) Copy this file and rename class/file.
2) Register your mob with @register_mob("YourMobType").
3) Implement animations and behavior hooks.
4) Optionally persist custom fields via save_state/load_state.
"""

from __future__ import annotations

from paths import textures_dir
from sprite_animation import SpriteAnimation

from mobs.mob import Mob
from mobs.registry import register_mob


@register_mob("MyNeutralMob")
class MyNeutralMob(Mob):
    """Neutral mob template.

    This class already plugs into:
    - Mob registry (for automatic save/load type resolution)
    - Base loot table support
    - Base serialization (position, velocity, health, current_animation_state, etc.)
    """

    def __init__(self, world, x: float, y: float, drop_table: dict[int, float] | None = None):
        # 1) Define your textures/animations.
        texture_dir = textures_dir("mobs", "my_neutral_mob")
        animations = {
            # Replace with your own states and frame files.
            "idle": SpriteAnimation([texture_dir / "idle.png"], fps=4.0, loop=True),
            "walking": SpriteAnimation([texture_dir / "walk_1.png", texture_dir / "walk_2.png"], fps=8.0, loop=True),
        }

        # 2) Optional default loot table.
        #    Keys are entry IDs (item or block), values are probabilities in [0.0, 1.0].
        loot_table = {} if drop_table is None else drop_table

        # 3) Call Mob constructor.
        super().__init__(
            world,
            x=x,
            y=y,
            animations=animations,
            default_state="idle",
            health=3,
            speed=90.0,
            drop_table=loot_table,
        )

        # 4) Add custom runtime fields here.
        self.mood_timer = 0.0

    def _update_unalerted_behavior(self, delta_time: float):
        """Optional: neutral movement while not threatened.

        Keep or replace this method depending on how your mob should move.
        """
        # Example: simple walk using base walk_direction.
        self.change_x = self.walk_direction * self.speed * 0.6
        if abs(self.change_x) > 0.1:
            self.set_animation_state("walking")
        else:
            self.set_animation_state("idle")

    def save_state(self) -> dict:
        """Persist only custom fields not already covered by Mob.to_save_data()."""
        return {
            "mood_timer": float(self.mood_timer),
        }

    def load_state(self, state: dict) -> None:
        """Restore custom fields saved by save_state()."""
        try:
            self.mood_timer = max(0.0, float(state.get("mood_timer", 0.0)))
        except (TypeError, ValueError):
            self.mood_timer = 0.0
