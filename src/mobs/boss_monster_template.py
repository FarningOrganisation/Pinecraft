"""Template for creating a new boss monster.

Usage:
1) Copy this file and rename class/file.
2) Register your boss with @register_mob("YourBossType") if it should be loadable from saves.
3) Implement boss state hooks (on_state_* and optional on_ai_state_enter/exit).
4) Decide persistence via should_save().
5) Optionally persist custom fields via save_state/load_state.
"""

from __future__ import annotations

from paths import textures_dir
from sprite_animation import SpriteAnimation

from mobs.boss_monster import BossMonster
from mobs.registry import register_mob


@register_mob("MyBoss")
class MyBoss(BossMonster):
    """Boss template with state-machine hooks.

    This class already plugs into:
    - Mob registry (automatic save/load type resolution)
    - Boss AI state machine (ai_state + phase_state)
    - Base serialization (position, velocity, health, current_animation_state, etc.)

    Important:
    - Registering enables restore from save data.
    - should_save() decides whether an instance is written into save payloads.
    """

    def __init__(self, world, x: float, y: float, drop_table: dict[int, float] | None = None):
        # 1) Define textures/animations for your boss.
        texture_dir = textures_dir("mobs", "my_boss")
        animations = {
            "idle": SpriteAnimation([texture_dir / "idle.png"], fps=4.0, loop=True),
            "walking": SpriteAnimation([texture_dir / "walk_1.png", texture_dir / "walk_2.png"], fps=8.0, loop=True),
            "windup": SpriteAnimation([texture_dir / "windup_1.png", texture_dir / "windup_2.png"], fps=10.0, loop=False),
            "attack": SpriteAnimation([texture_dir / "attack_1.png", texture_dir / "attack_2.png"], fps=12.0, loop=False),
            "recover": SpriteAnimation([texture_dir / "recover.png"], fps=6.0, loop=False),
            "stunned": SpriteAnimation([texture_dir / "stunned.png"], fps=4.0, loop=True),
        }

        # 2) Optional default loot table.
        loot_table = {} if drop_table is None else drop_table

        # 3) Call BossMonster constructor with tuning values.
        super().__init__(
            world,
            x=x,
            y=y,
            animations=animations,
            default_state="idle",
            health=60,
            activate_range=560.0,
            aggro_duration=5.0,
            attack_range=44.0,
            speed=105.0,
            damage=4,
            drop_table=loot_table,
        )

        # 4) Optional boss-specific phase thresholds.
        self.phase2_health_ratio = 0.65
        self.enraged_health_ratio = 0.28

        # 5) Custom runtime fields.
        self.special_cooldown = 0.0
        self.rage_stacks = 0

    def should_save(self) -> bool:
        """Decide boss persistence.

        Option A: return bool(self.alive) for persistent bosses.
        Option B: return False for ritual/rechannel-only bosses.
        """
        return False

    def on_ai_state_enter(self, previous_state: str, next_state: str) -> None:
        """Optional: react to state transitions."""
        if next_state == self.AI_WINDUP:
            # Example: prep a telegraphed attack.
            self.special_cooldown = max(self.special_cooldown, 0.25)

    def on_state_chase(self, player, delta_time: float) -> None:
        """Override chase behavior while keeping base movement logic."""
        super().on_state_chase(player, delta_time)
        if self.phase_state == self.PHASE_ENRAGED:
            self.change_x *= 1.08

    def on_state_attack(self, player, delta_time: float) -> None:
        """Override attack behavior for custom boss mechanics."""
        super().on_state_attack(player, delta_time)

        self.special_cooldown = max(0.0, self.special_cooldown - delta_time)
        if self.special_cooldown <= 0.0:
            # Example: trigger a special effect/projectile burst here.
            self.rage_stacks += 1
            self.special_cooldown = 1.2 if self.phase_state != self.PHASE_ENRAGED else 0.8

    def save_state(self) -> dict:
        """Persist only custom fields not already covered by base classes."""
        return {
            "special_cooldown": float(self.special_cooldown),
            "rage_stacks": int(self.rage_stacks),
        }

    def load_state(self, state: dict) -> None:
        """Restore custom fields saved by save_state()."""
        try:
            self.special_cooldown = max(0.0, float(state.get("special_cooldown", 0.0)))
        except (TypeError, ValueError):
            self.special_cooldown = 0.0

        try:
            self.rage_stacks = max(0, int(state.get("rage_stacks", 0)))
        except (TypeError, ValueError):
            self.rage_stacks = 0
