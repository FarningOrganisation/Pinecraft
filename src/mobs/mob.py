"""Base enemy logic and slime enemy implementation for Pinecraft."""

from __future__ import annotations

from animated_sprite import AnimatedSprite
from blocks import AIR, is_block_solid
from settings import GRAVITY, TILE_SIZE
from typing import Callable, cast
import random


class Mob(AnimatedSprite):
    """Shared mob behavior for creature-like actors in the world."""

    MOB_TYPE = "Mob"

    def __init__(
        self,
        world,
        x: float,
        y: float,
        animations,
        default_state,
        health: int = 3,
        speed: float = 90.0,
        drop_table: dict[int, float] | None = None,
    ):
        super().__init__(animations=animations, default_state=default_state, facing_right=True)

        self.world = world
        self.max_health = max(1, health)
        self.health = self.max_health
        self.speed = speed

        self.vanish_after_death_timer = 0.5
        self.damage_flash_timer = 0.0

        self.change_x = 0.0
        self.change_y = 0.0
        self.on_ground = False
        self.stun_timer = 0.0
        self.flee_timer = 0.0
        self.walk_direction = 1
        self.jump_strength = 350.0
        self.alive = True
        self.drop_table = self._sanitize_drop_table(drop_table)
        self.pending_item_drops: list[tuple[int, float, float]] = []
        self._death_drops_spawned = False

        if self.current_animation is None or not self.current_animation.frames:
            raise ValueError("Mob requires at least one animation frame")
        current_frame = self.current_animation.frames[0]
        self.width = current_frame.width
        self.height = current_frame.height
        self.collision_width = current_frame.width
        self.collision_height = current_frame.height
        self.center_x = x
        self.center_y = y

    def _grounded_below(self) -> bool:
        """True when there is a solid block directly beneath the enemy."""
        if self.world is None:
            return False

        left = self.center_x - self.collision_width / 2 + 2.0
        right = self.center_x + self.collision_width / 2 - 2.0
        probe_y = int((self.center_y - self.collision_height / 2 - 1.0) // TILE_SIZE)

        for tile_x in range(int(left // TILE_SIZE), int(right // TILE_SIZE) + 1):
            block_id = self.world.get_block(tile_x, probe_y, generate_if_missing=False)
            if block_id != AIR and is_block_solid(block_id):
                return True
        return False

    def player_direction(self, player) -> int:
        """Returns -1 or 1 based on the player's x-position relative to this enemy."""
        if player is None:
            return 0
        return 1 if player.center_x >= self.center_x else -1

    def apply_knockback(self, knockback_x: float, knockback_y: float, stun_duration: float = 0.2):
        """Wendet Rückstoß und einen kurzen Stun an."""
        self.change_x = knockback_x
        self.change_y = max(self.change_y, knockback_y)
        self.stun_timer = max(self.stun_timer, stun_duration)
        self.flee_timer = max(self.flee_timer, 1.0)
        self.on_ground = False

    def on_death(self):
        """Queues item drops based on this mob's drop table."""
        if self._death_drops_spawned:
            return None

        self._death_drops_spawned = True
        if not self.drop_table:
            return None

        spawn_x = float(self.center_x)
        spawn_y = float(self.center_y)
        jitter = TILE_SIZE * 0.25

        for entry_id, probability in self.drop_table.items():
            if random.random() > probability:
                continue
            self.pending_item_drops.append(
                (
                    entry_id,
                    spawn_x + random.uniform(-jitter, jitter),
                    spawn_y + random.uniform(-jitter, jitter),
                )
            )
        return None

    @staticmethod
    def _sanitize_drop_table(drop_table: dict[int, float] | None) -> dict[int, float]:
        """Normalizes drop chances to valid item IDs and probabilities in [0, 1]."""
        if not isinstance(drop_table, dict):
            return {}

        sanitized: dict[int, float] = {}
        for entry_id, probability in drop_table.items():
            if not isinstance(entry_id, int):
                continue
            if not isinstance(probability, (int, float)):
                continue
            sanitized[entry_id] = max(0.0, min(1.0, float(probability)))
        return sanitized

    @staticmethod
    def _decode_drop_table(raw_drop_table) -> dict[int, float]:
        """Decodes saved drop tables from list or dict formats."""
        if isinstance(raw_drop_table, dict):
            return Mob._sanitize_drop_table(raw_drop_table)

        if not isinstance(raw_drop_table, list):
            return {}

        decoded: dict[int, float] = {}
        for entry in raw_drop_table:
            if not isinstance(entry, (list, tuple)) or len(entry) != 2:
                continue
            try:
                entry_id = int(entry[0])
                chance = float(entry[1])
            except (TypeError, ValueError):
                continue
            decoded[entry_id] = max(0.0, min(1.0, chance))
        return decoded

    @staticmethod
    def _encode_drop_table(drop_table: dict[int, float]) -> list[list[float]]:
        """Encodes drop tables into a stable JSON-friendly list format."""
        return [[int(entry_id), float(chance)] for entry_id, chance in sorted(drop_table.items())]

    def save_state(self) -> dict:
        """Hook for subclasses to persist extra state beyond the common mob fields."""
        return {}

    def should_save(self) -> bool:
        """Hook: entscheidet, ob dieser Mob im Save landen soll."""
        return bool(getattr(self, "alive", True))

    def load_state(self, state: dict) -> None:
        """Hook for subclasses to restore extra state from save data."""
        return None

    def to_save_data(self) -> dict:
        """Serializes base mob state; subclasses can extend via save_state()."""
        health = int(getattr(self, "health", 1))
        max_health = max(1, int(getattr(self, "max_health", health)))
        payload = {
            "mob_type": str(getattr(self.__class__, "MOB_TYPE", self.__class__.__name__)),
            "position": {
                "x": float(getattr(self, "center_x", 0.0)),
                "y": float(getattr(self, "center_y", 0.0)),
            },
            "velocity": {
                "x": float(getattr(self, "change_x", 0.0)),
                "y": float(getattr(self, "change_y", 0.0)),
            },
            "health": max(0, min(max_health, health)),
            "max_health": max_health,
            "facing_right": bool(getattr(self, "facing_right", True)),
            "walk_direction": -1 if int(getattr(self, "walk_direction", 1)) < 0 else 1,
            "stun_timer": max(0.0, float(getattr(self, "stun_timer", 0.0))),
            "flee_timer": max(0.0, float(getattr(self, "flee_timer", 0.0))),
            "current_animation_state": str(getattr(self, "current_animation_state", "")),
            "drop_table": self._encode_drop_table(self.drop_table),
        }

        custom_state = self.save_state()
        if isinstance(custom_state, dict) and custom_state:
            payload["custom_state"] = custom_state
        return payload

    @classmethod
    def from_save_data(cls, world, data: dict):
        """Creates and restores a mob instance from save data."""
        position = data.get("position", {}) if isinstance(data, dict) else {}
        if not isinstance(position, dict):
            position = {}

        center_x = float(position.get("x", 0.0))
        center_y = float(position.get("y", 0.0))
        drop_table = cls._decode_drop_table(data.get("drop_table"))

        create_mob = cast(Callable[..., Mob], cls)
        mob = create_mob(world, x=center_x, y=center_y, drop_table=drop_table)
        mob.apply_save_data(data)
        return mob

    def apply_save_data(self, data: dict) -> None:
        """Applies common saved mob state to an existing instance."""
        velocity = data.get("velocity", {}) if isinstance(data, dict) else {}
        if not isinstance(velocity, dict):
            velocity = {}

        max_health = max(1, int(data.get("max_health", getattr(self, "max_health", 1))))
        health = int(data.get("health", max_health))
        self.max_health = max_health
        self.health = max(0, min(max_health, health))
        self.alive = self.health > 0

        self.change_x = float(velocity.get("x", 0.0))
        self.change_y = float(velocity.get("y", 0.0))
        self.facing_right = bool(data.get("facing_right", True))
        self.walk_direction = -1 if int(data.get("walk_direction", 1)) < 0 else 1
        self.stun_timer = max(0.0, float(data.get("stun_timer", 0.0)))
        self.flee_timer = max(0.0, float(data.get("flee_timer", 0.0)))
        self.drop_table = self._decode_drop_table(data.get("drop_table"))

        saved_state = data.get("current_animation_state")
        if isinstance(saved_state, str) and saved_state in self.animations:
            self.set_animation_state(saved_state)

        custom_state = data.get("custom_state", {})
        if isinstance(custom_state, dict):
            self.load_state(custom_state)

    def consume_pending_item_drops(self) -> list[tuple[int, float, float]]:
        """Returns and clears queued world-space item drops."""
        if not self.pending_item_drops:
            return []
        pending = self.pending_item_drops
        self.pending_item_drops = []
        return pending

    def apply_physics(self, delta_time: float) -> bool:
        """Applies gravity and block collisions to this mob."""
        previous_left = self.center_x - self.collision_width / 2
        previous_right = self.center_x + self.collision_width / 2
        previous_bottom = self.center_y - self.collision_height / 2
        previous_top = self.center_y + self.collision_height / 2

        was_grounded = self._grounded_below()
        self.on_ground = was_grounded

        if not was_grounded or self.change_y > 0.0:
            self.change_y -= GRAVITY * delta_time
        elif self.change_y < 0.0:
            self.change_y = 0.0

        self.center_x += self.change_x * delta_time
        self._resolve_horizontal_collision(previous_left, previous_right)

        self.center_y += self.change_y * delta_time
        self.on_ground = False
        self._resolve_vertical_collision(previous_bottom, previous_top)
        self._resolve_embedded_collision()

        if self._grounded_below():
            self.on_ground = True
            if self.change_y < 0.0:
                self.change_y = 0.0

        return self.on_ground

    def _resolve_embedded_collision(self, max_passes: int = 3):
        """Löst verbleibende Überlappungen, falls ein Mob in Blöcken feststeckt."""
        world = self.world
        if world is None:
            return

        skin = 0.25
        for _ in range(max(1, int(max_passes))):
            left = self.center_x - self.collision_width / 2
            right = self.center_x + self.collision_width / 2
            bottom = self.center_y - self.collision_height / 2
            top = self.center_y + self.collision_height / 2

            moved = False
            for _tile_x, _tile_y, block_left, block_right, block_bottom, block_top in world.get_blocks_around(
                left, right, bottom, top
            ):
                overlap_x = min(right, block_right) - max(left, block_left)
                overlap_y = min(top, block_top) - max(bottom, block_bottom)
                if overlap_x <= 0.0 or overlap_y <= 0.0:
                    continue

                block_center_x = (block_left + block_right) * 0.5
                block_center_y = (block_bottom + block_top) * 0.5

                # Bevorzuge vertikales Entklemmen leicht, um "im Boden stecken" stabil zu lösen.
                if overlap_y <= overlap_x + 0.5:
                    if self.center_y >= block_center_y:
                        self.center_y += overlap_y + skin
                        self.on_ground = True
                    else:
                        self.center_y -= overlap_y + skin
                    self.change_y = 0.0
                else:
                    if self.center_x >= block_center_x:
                        self.center_x += overlap_x + skin
                    else:
                        self.center_x -= overlap_x + skin
                    self.change_x = 0.0

                moved = True
                break

            if not moved:
                break

    def _resolve_horizontal_collision(self, previous_left: float, previous_right: float):
        """Keeps the mob inside solid blocks on the x-axis."""
        world = self.world
        if world is None:
            return

        left = self.center_x - self.collision_width / 2
        right = self.center_x + self.collision_width / 2
        bottom = self.center_y - self.collision_height / 2
        top = self.center_y + self.collision_height / 2
        skin = 0.25

        for _, _, block_x_min, block_x_max, block_y_min, block_y_max in world.get_blocks_around(left, right, bottom, top):
            if not (bottom + skin < block_y_max and top - skin > block_y_min):
                continue
            if self.change_x > 0 and previous_right <= block_x_min:
                self.center_x = block_x_min - self.collision_width / 2 - skin
                self.change_x = 0.0
            elif self.change_x < 0 and previous_left >= block_x_max:
                self.center_x = block_x_max + self.collision_width / 2 + skin
                self.change_x = 0.0

    def _resolve_vertical_collision(self, previous_bottom: float, previous_top: float):
        """Keeps the mob inside solid blocks on the y-axis."""
        world = self.world
        if world is None:
            return

        left = self.center_x - self.collision_width / 2
        right = self.center_x + self.collision_width / 2
        bottom = self.center_y - self.collision_height / 2
        top = self.center_y + self.collision_height / 2
        skin = 0.25

        for _, _, block_x_min, block_x_max, block_y_min, block_y_max in world.get_blocks_around(left, right, bottom, top):
            if not (left + skin < block_x_max and right - skin > block_x_min):
                continue
            if self.change_y > 0 and previous_top <= block_y_min:
                self.center_y = block_y_min - self.collision_height / 2 - skin
                self.change_y = 0.0
            elif self.change_y < 0 and previous_bottom >= block_y_max:
                self.center_y = block_y_max + self.collision_height / 2 + skin
                self.change_y = 0.0
                self.on_ground = True

    def _has_wall_in_front(self, direction: int) -> bool:
        """True if there is a solid block directly in front of the mob."""
        if self.world is None:
            return False

        probe_x = self.center_x + direction * (self.collision_width * 0.7 + 6.0)
        probe_y = self.center_y - self.collision_height * 0.15
        tile_x = int(probe_x // TILE_SIZE)
        tile_y = int(probe_y // TILE_SIZE)
        block_id = self.world.get_block(tile_x, tile_y, generate_if_missing=False)
        return block_id != AIR and is_block_solid(block_id)

    def _can_jump_over_obstacle(self, direction: int) -> bool:
        """Checks whether there is room above one forward obstacle probe."""
        if self.world is None:
            return False

        probe_x = int((self.center_x + direction * (self.collision_width * 0.7 + TILE_SIZE)) // TILE_SIZE)
        probe_y = int((self.center_y + self.collision_height * 0.5 + 8.0) // TILE_SIZE)
        block_id = self.world.get_block(probe_x, probe_y, generate_if_missing=False)
        return block_id == AIR or not is_block_solid(block_id)

    def _has_headroom_for_jump(self, min_tiles: int = 2) -> bool:
        """True, wenn ueber dem Mob genug freier Raum fuer einen Sprung ist."""
        if self.world is None:
            return False

        left = self.center_x - self.collision_width / 2 + 2.0
        right = self.center_x + self.collision_width / 2 - 2.0
        start_tile_y = int((self.center_y + self.collision_height / 2 + 1.0) // TILE_SIZE)

        for tile_x in range(int(left // TILE_SIZE), int(right // TILE_SIZE) + 1):
            for dy in range(max(1, int(min_tiles))):
                block_id = self.world.get_block(tile_x, start_tile_y + dy, generate_if_missing=False)
                if block_id != AIR and is_block_solid(block_id):
                    return False
        return True

    def _is_trapped_in_narrow_pit(self) -> bool:
        """True, wenn links und rechts auf Bodenhoehe Wände stehen (typisch 1x1-Loch)."""
        return self._grounded_below() and self._has_wall_in_front(1) and self._has_wall_in_front(-1)

    def _try_pit_escape_jump(self) -> bool:
        """Versucht einen gezielten Sprung aus einem schmalen Loch."""
        if not self._has_headroom_for_jump(min_tiles=2):
            return False

        can_right = self._can_jump_over_obstacle(1)
        can_left = self._can_jump_over_obstacle(-1)

        if can_right and not can_left:
            direction = 1
        elif can_left and not can_right:
            direction = -1
        elif can_left and can_right:
            direction = self.walk_direction if self.walk_direction in (-1, 1) else random.choice((-1, 1))
        else:
            direction = self.walk_direction if self.walk_direction in (-1, 1) else 1

        self.walk_direction = direction
        self.facing_right = direction >= 0
        self.change_y = self.jump_strength * (1.0 + random.random() * 0.15)
        self.change_x = direction * self.speed * 0.35
        return True

    def _update_unalerted_behavior(self, delta_time: float):
        """Default unalerted AI: wander, jump over obstacles, and turn around at walls."""
        self.facing_right = self.walk_direction >= 0
        grounded = self._grounded_below()

        # In engen Loechern nicht hektisch links/rechts flippen, sondern gezielt raus springen.
        if self._is_trapped_in_narrow_pit():
            if self._try_pit_escape_jump():
                return
            # Ohne Cooldown weiterlaufen, damit auf der naechsten freien Gelegenheit
            # sofort erneut gesprungen werden kann.

        if grounded and self._has_wall_in_front(self.walk_direction):
            can_jump = self._can_jump_over_obstacle(self.walk_direction)

            if can_jump:
                jump_factor = 0.9 + random.random() * 0.2
                self.change_y = max(self.change_y, self.jump_strength * jump_factor)
                self.change_x = self.walk_direction * self.speed * 0.8
                return

            self.walk_direction *= -1
            self.change_x = self.walk_direction * self.speed * 0.6
            return

        self.change_x = self.walk_direction * self.speed * 0.75

    def _is_player_threatening(self, player) -> bool:
        """Neutral mobs flee only after they were attacked."""
        return player is not None and self.flee_timer > 0.0

    def _update_alerted_behavior(self, player, delta_time: float, *, speed: float | None = None):
        """Default neutral response: flee away from the player."""
        if player is None:
            return

        direction_away = -self.player_direction(player)
        self.facing_right = direction_away >= 0
        effective_speed = self.speed if speed is None else speed
        self.change_x = direction_away * effective_speed

    def update_ai(self, delta_time: float, player):
        """Default AI is neutral: flee when threatened, otherwise wander."""
        if not self.alive:
            self.vanish_after_death_timer = max(0.0, self.vanish_after_death_timer - delta_time)
            return

        if self.stun_timer > 0.0:
            self.stun_timer = max(0.0, self.stun_timer - delta_time)
            self.change_x *= 0.9
            return

        if self.flee_timer > 0.0:
            self.flee_timer = max(0.0, self.flee_timer - delta_time)

        self.alerted = self._is_player_threatening(player)
        if self.alerted and player is not None:
            self._update_alerted_behavior(player, delta_time)
            return

        self._update_unalerted_behavior(delta_time)
        self.alerted = False

    def update(self, delta_time: float, player=None):
        """Default mob update: AI -> physics -> animation plus a brief damage tint."""
        if self.damage_flash_timer > 0.0:
            self.damage_flash_timer = max(0.0, self.damage_flash_timer - delta_time)
            if self.damage_flash_timer > 0.0:
                self.color = (255, 120, 120)
            else:
                self.color = (255, 255, 255)

        if player is not None:
            self.update_ai(delta_time, player)
        self.apply_physics(delta_time)
        super().update(delta_time)

    def take_damage(self, amount: int) -> bool:
        """Apply damage and return whether the enemy was killed."""
        if not self.alive:
            return False

        self.health -= amount
        self.damage_flash_timer = 0.15
        self.on_take_damage(amount)
        if self.health <= 0:
            self.health = 0
            self.alive = False
            self.on_death()
            return True

        self.flee_timer = max(self.flee_timer, 1.4)
        return False

    # function zum Überschreiben
    def on_take_damage(self, amount):
        pass





Enemy = Mob
