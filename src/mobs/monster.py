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
        attack_range: float = 32.0,
        speed: float = 90.0,
        damage: int = 1,
    ):
        super().__init__(world, x=x, y=y, health=health, speed=speed, animations=animations, default_state=default_state)
        self.activate_range = activate_range
        self.attack_range = attack_range
        self.damage = damage
        self.contact_cooldown = 0.0
        self.alerted = False

    def _can_see_player(self, player) -> bool:
        """Player is close enough to trigger hostile behavior."""
        if player is None:
            return False
        dx = player.center_x - self.center_x
        dy = player.center_y - self.center_y
        distance = math.hypot(dx, dy)
        return distance <= self.activate_range or self.aggro_timer > 0.0

    def move_toward_player(self, player, delta_time: float, *, speed: float | None = None):
        """Generic horizontal movement toward the player without jumping behavior."""
        if player is None:
            return

        direction = self.player_direction(player)
        self.facing_right = direction >= 0
        effective_speed = self.speed if speed is None else speed
        dx = abs(player.center_x - self.center_x)
        if dx <= self.attack_range:
            self.change_x = 0.0
            return

        self.change_x = direction * effective_speed

        if self.center_y < 0:
            self.center_y = 0.0

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

    def update_ai(self, delta_time: float, player):
        """Hostile default AI: chase player in range, otherwise wander."""
        if not self.alive:
            self.vanish_after_death_timer = max(0.0, self.vanish_after_death_timer - delta_time)
            return

        if self.stun_timer > 0.0:
            self.stun_timer = max(0.0, self.stun_timer - delta_time)
            self.change_x *= 0.9
            return

        if self.aggro_timer > 0.0:
            self.aggro_timer = max(0.0, self.aggro_timer - delta_time)

        self.alerted = self._can_see_player(player)
        if self.alerted:
            self.move_toward_player(player, delta_time)
            move_state = self._preferred_move_state()
            if move_state is not None:
                self.set_state(move_state)
            return

        self._update_wander_behavior(delta_time)
        if abs(self.change_x) > 0.1:
            move_state = self._preferred_move_state()
            if move_state is not None:
                self.set_state(move_state)
        else:
            idle_state = self._preferred_idle_state()
            if idle_state is not None:
                self.set_state(idle_state)

    def update(self, delta_time: float, player=None):
        """Monster update: shared mob logic + attack contact damage."""
        super().update(delta_time, player)
        if player is not None:
            self.handle_contact_damage(player, delta_time)

    def handle_contact_damage(self, player, delta_time: float) -> None:
        """Damages the player on direct contact within range."""
        if player is None or not self.alive or self.stun_timer > 0.0:
            return

        mob_box = aabb_from_center(self.center_x, self.center_y, self.collision_width, self.collision_height)
        player_box = aabb_from_center(player.center_x, player.center_y, player.collision_width, player.collision_height)
        if aabb_overlap(mob_box, player_box) and hasattr(player, "take_damage"):
            player.take_damage(self.damage)
