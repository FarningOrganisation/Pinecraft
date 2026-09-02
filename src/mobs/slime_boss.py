"""Slime boss that splits into smaller slimes on death."""

from __future__ import annotations

from ids import CHARCOAL
from mobs.registry import register_mob
from mobs.slime import Slime


@register_mob("SlimeBoss")
class SlimeBoss(Slime):
    """A large slime that keeps the normal slime jump behavior and splits on death."""

    STAGE_BIG = "big"
    STAGE_MEDIUM = "medium"

    def __init__(
        self,
        world,
        x: float,
        y: float,
        health: int | None = None,
        split_stage: str = STAGE_BIG,
        drop_table: dict[int, float] | None = None,
    ):
        stage = str(split_stage or self.STAGE_BIG).strip().lower()
        if stage not in (self.STAGE_BIG, self.STAGE_MEDIUM):
            stage = self.STAGE_BIG

        if health is None:
            health = 14 if stage == self.STAGE_BIG else 7

        loot_table = {CHARCOAL: 0.1} if drop_table is None else drop_table
        super().__init__(world, x=x, y=y, health=health, drop_table=loot_table)

        self.split_stage = stage
        self.pending_mob_spawns: list[tuple[type, float, float, dict]] = []
        self._split_spawned = False
        self._apply_stage_stats()

    def should_save(self) -> bool:
        """Boss encounter is re-triggered instead of persisted mid-fight."""
        return False

    def _apply_stage_stats(self) -> None:
        """Applies stage-specific size and stronger jump stats."""
        if self.split_stage == self.STAGE_BIG:
            self.scale = 3.2
            self.jump_speed = 760.0
            self.jump_forward_speed = 235.0
            self.damage = 2
        else:
            self.scale = 2.45
            self.jump_speed = 660.0
            self.jump_forward_speed = 195.0
            self.damage = 1
        self.collision_width = self.width
        self.collision_height = self.height

    def _queue_spawn(self, mob_class: type, spawn_x: float, spawn_y: float, **mob_kwargs) -> None:
        """Queues mob spawns for GameView to materialize after update."""
        self.pending_mob_spawns.append((mob_class, float(spawn_x), float(spawn_y), dict(mob_kwargs)))

    def _queue_split_children(self) -> None:
        """Queues next split stage entities."""
        base_x = float(self.center_x)
        base_y = float(self.center_y)

        if self.split_stage == self.STAGE_BIG:
            spread = 26.0
            self._queue_spawn(SlimeBoss, base_x - spread, base_y, split_stage=self.STAGE_MEDIUM, health=7)
            self._queue_spawn(SlimeBoss, base_x + spread, base_y, split_stage=self.STAGE_MEDIUM, health=7)
            return

        if self.split_stage == self.STAGE_MEDIUM:
            spread = 16.0
            self._queue_spawn(Slime, base_x - spread, base_y, health=3)
            self._queue_spawn(Slime, base_x + spread, base_y, health=3)

    def on_death(self):
        """Drops loot and queues split children exactly once."""
        super().on_death()
        if self._split_spawned:
            return None
        self._split_spawned = True
        self._queue_split_children()
        return None

    def consume_pending_mob_spawns(self) -> list[tuple[type, float, float, dict]]:
        """Returns and clears queued mob spawns."""
        if not self.pending_mob_spawns:
            return []
        pending = self.pending_mob_spawns
        self.pending_mob_spawns = []
        return pending

    def save_state(self) -> dict:
        """Persists stage-specific fields (if persistence is enabled later)."""
        payload = super().save_state()
        payload.update(
            {
            "split_stage": str(self.split_stage),
            "split_spawned": bool(self._split_spawned),
            }
        )
        return payload

    def load_state(self, state: dict) -> None:
        """Restores stage-specific fields."""
        super().load_state(state)
        split_stage = state.get("split_stage", self.split_stage)
        if isinstance(split_stage, str) and split_stage in (self.STAGE_BIG, self.STAGE_MEDIUM):
            self.split_stage = split_stage

        self._split_spawned = bool(state.get("split_spawned", self._split_spawned))
        self._apply_stage_stats()
