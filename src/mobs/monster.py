from mobs.mob import Mob
from physics import aabb_from_center, aabb_overlap
import math


class Monster(Mob):
    """A mob that can detect, chase, and damage the player."""

    def __init__(
        self,
        world,
        x: float,
        y: float,
        animations,
        default_state,
        health: int = 3,
        activate_range: float = 260.0,
        aggro_duration: float = 2.0,
        attack_range: float | None = None,
        speed: float = 90.0,
        damage: int = 1,
        drop_table: dict[int, float] | None = None,
    ):
        super().__init__(
            world,
            x=x,
            y=y,
            health=health,
            speed=speed,
            animations=animations,
            default_state=default_state,
            drop_table=drop_table,
        )
        self.activate_range = activate_range
        self.aggro_duration = max(0.0, aggro_duration)
        self.aggro_timer = self.aggro_duration
        self.attack_range = attack_range
        self.damage = damage
        self.contact_cooldown = 0.0
        self.alerted = False

    def _can_see_player(self, player) -> bool:
        """Player is inside the immediate monster activation range."""
        if player is None:
            return False
        dx = player.center_x - self.center_x
        dy = player.center_y - self.center_y
        distance = math.hypot(dx, dy)
        return distance <= self.activate_range

    def _update_alerted_behavior(self, player, delta_time: float, *, speed: float | None = None):
        """Default alerted behavior: move horizontally toward the player."""
        if player is None:
            return

        direction = self.player_direction(player)
        self.facing_right = direction >= 0
        effective_speed = self.speed if speed is None else speed
        if self._is_player_in_attack_range(player):
            self.change_x = 0.0
            return

        self.change_x = direction * effective_speed

        if self.center_y < 0:
            self.center_y = 0.0

    def _update_attack_behavior(self, player, delta_time: float):
        """Optional attack hook for subclasses (e.g., ranged or AoE attacks)."""
        return None

    def _is_touching_player(self, player) -> bool:
        """True when the collision boxes of monster and player overlap."""
        if player is None:
            return False

        mob_box = aabb_from_center(self.center_x, self.center_y, self.collision_width, self.collision_height)
        player_box = aabb_from_center(player.center_x, player.center_y, player.collision_width, player.collision_height)
        return aabb_overlap(mob_box, player_box)

    def _is_player_in_attack_range(self, player) -> bool:
        """Uses AABB touch by default; optional attack_range enables distance attacks."""
        if player is None:
            return False

        if self.attack_range is None:
            return self._is_touching_player(player)

        dx = player.center_x - self.center_x
        dy = player.center_y - self.center_y
        distance = math.hypot(dx, dy)
        return distance <= self.attack_range

    def _preferred_move_state(self) -> str | None:
        """Wählt einen verfügbaren Bewegungszustand für Monster-Animationen."""
        if "walking" in self.animations:
            return "walking"
        if "move" in self.animations:
            return "move"
        return None

    def _preferred_idle_state(self) -> str | None:
        """Wählt einen verfügbaren Idle-Zustand."""
        if "idle" in self.animations:
            return "idle"
        return self._preferred_move_state()

    def _refresh_ground_state_for_ai(self):
        """Synchronisiert Bodenkontakt vor AI-Entscheidungen."""
        self.on_ground = self.on_ground or self._grounded_below()
        if self.on_ground and self.change_y < 0.0:
            self.change_y = 0.0

    def update_ai(self, delta_time: float, player):
        """Hostile default AI: chase player in range, otherwise wander."""
        if not self.alive:
            self.vanish_after_death_timer = max(0.0, self.vanish_after_death_timer - delta_time)
            return

        if self.stun_timer > 0.0:
            self.stun_timer = max(0.0, self.stun_timer - delta_time)
            self.change_x *= 0.9
            return

        self._refresh_ground_state_for_ai()

        in_activate_range = self._can_see_player(player)
        if in_activate_range:
            self.aggro_timer = self.aggro_duration
            self.alerted = True
        else:
            if self.aggro_timer > 0.0:
                self.aggro_timer = max(0.0, self.aggro_timer - delta_time)
            self.alerted = self.aggro_timer > 0.0
            if not self.alerted:
                self.aggro_timer = self.aggro_duration

        if self.alerted:
            self._update_alerted_behavior(player, delta_time)
            if self._is_player_in_attack_range(player):
                self._update_attack_behavior(player, delta_time)
            move_state = self._preferred_move_state()
            if move_state is not None:
                self.set_animation_state(move_state)
            return

        self._update_unalerted_behavior(delta_time)
        if abs(self.change_x) > 0.1:
            move_state = self._preferred_move_state()
            if move_state is not None:
                self.set_animation_state(move_state)
        else:
            idle_state = self._preferred_idle_state()
            if idle_state is not None:
                self.set_animation_state(idle_state)

    def update(self, delta_time: float, player=None):
        """Monster update: shared mob logic + attack contact damage."""
        super().update(delta_time, player)
        if player is not None:
            self.handle_contact_damage(player, delta_time)

    def handle_contact_damage(self, player, delta_time: float) -> None:
        """Damages the player on direct contact."""
        if player is None or not self.alive or self.stun_timer > 0.0:
            return

        if self._is_touching_player(player) and hasattr(player, "take_damage"):
            player.take_damage(self.damage)
