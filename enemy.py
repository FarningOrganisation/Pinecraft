"""Base enemy logic and slime enemy implementation for Pinecraft."""

from __future__ import annotations

import math

from animated_sprite import AnimatedSprite
from blocks import AIR, is_block_solid
from items import TORCH
from settings import GRAVITY, TILE_SIZE
from sprite_animation import SpriteAnimation


class Enemy(AnimatedSprite):
    """Shared enemy behavior for creature-like actors in the world."""

    def __init__(
        self,
        world,
        x: float,
        y: float,
        health: int = 3,
        activate_range: float = 260.0,
        attack_range: float = 32.0,
        speed: float = 90.0,
        damage: int = 1,
    ):
        super().__init__(animations={}, default_state="idle", facing_right=True)

        self.world = world
        self.max_health = max(1, health)
        self.health = self.max_health
        self.activate_range = activate_range
        self.attack_range = attack_range
        self.speed = speed
        self.damage = damage

        self.change_x = 0.0
        self.change_y = 0.0
        self.on_ground = False
        self.alerted = False
        self.contact_cooldown = 0.0
        self.stun_timer = 0.0
        self.aggro_timer = 0.0
        self.alive = True

        self.width = 28
        self.height = 28
        self.collision_width = 28
        self.collision_height = 28
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

    def _can_see_player(self, player) -> bool:
        """Player is close enough to trigger the enemy."""
        if player is None:
            return False
        dx = player.center_x - self.center_x
        dy = player.center_y - self.center_y
        distance = math.hypot(dx, dy)
        return distance <= self.activate_range or self.aggro_timer > 0.0

    def player_direction(self, player) -> int:
        """Returns -1 or 1 based on the player's x-position relative to this enemy."""
        if player is None:
            return 0
        return 1 if player.center_x >= self.center_x else -1

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

    def apply_knockback(self, knockback_x: float, knockback_y: float, stun_duration: float = 0.2):
        """Wendet Rückstoß und einen kurzen Stun an."""
        self.change_x = knockback_x
        self.change_y = max(self.change_y, knockback_y)
        self.stun_timer = max(self.stun_timer, stun_duration)
        self.aggro_timer = max(self.aggro_timer, 2.0)
        self.on_ground = False

    def on_death(self):
        """Hook for subclasses when the enemy dies."""
        return None

    def handle_contact_damage(self, player, delta_time: float) -> None:
        """Damages the player on direct contact with a short cooldown."""
        if player is None or not self.alive or self.stun_timer > 0.0:
            return

        self.contact_cooldown = max(0.0, self.contact_cooldown - delta_time)
        if self.contact_cooldown > 0.0:
            return

        dx = abs(player.center_x - self.center_x)
        dy = abs(player.center_y - self.center_y)
        if dx < (player.width * 0.65 + self.width * 0.65) and dy < (player.height * 0.65 + self.height * 0.65):
            if hasattr(player, "health"):
                player.health = max(0, player.health - self.damage)
            self.contact_cooldown = 1.0

    def update_ai(self, delta_time: float, player):
        """Generic base update hook. Children can override movement logic if needed."""
        if not self.alive:
            return

        if self.stun_timer > 0.0:
            self.stun_timer = max(0.0, self.stun_timer - delta_time)

        if self.aggro_timer > 0.0:
            self.aggro_timer = max(0.0, self.aggro_timer - delta_time)

        self.alerted = self._can_see_player(player)
        self.handle_contact_damage(player, delta_time)
        super().update(delta_time)

    def take_damage(self, amount: int) -> bool:
        """Apply damage and return whether the enemy was killed."""
        if not self.alive:
            return False

        self.health -= amount
        if self.health <= 0:
            self.health = 0
            self.alive = False
            self.on_death()
            return True

        self.aggro_timer = max(self.aggro_timer, 2.5)
        return False
