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
        if dx <= 0:
            return

        step = min(dx, effective_speed * delta_time)
        self.center_x += direction * step
        self.change_x = direction * effective_speed

        if self.center_y < 0:
            self.center_y = 0.0

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
