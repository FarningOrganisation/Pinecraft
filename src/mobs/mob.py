"""Base enemy logic and slime enemy implementation for Pinecraft."""

from __future__ import annotations

import math

from animated_sprite import AnimatedSprite
from blocks import AIR, is_block_solid
from settings import GRAVITY, TILE_SIZE


class Mob(AnimatedSprite):
    """Shared mob behavior for creature-like actors in the world."""

    def __init__(
        self,
        world,
        x: float,
        y: float,
        health: int = 3,
        speed: float = 90.0,
    ):
        super().__init__(animations={}, default_state="idle", facing_right=True)

        self.world = world
        self.max_health = max(1, health)
        self.health = self.max_health
        self.speed = speed

        self.change_x = 0.0
        self.change_y = 0.0
        self.on_ground = False
        self.stun_timer = 0.0
        self.aggro_timer = 0.0
        self.walk_direction = 1
        self.jump_strength = 330.0
        self.jump_cooldown = 0.0
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
        self.aggro_timer = max(self.aggro_timer, 2.0)
        self.on_ground = False

    def on_death(self):
        """Hook for subclasses when the mob dies."""
        return None

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

        if self._grounded_below():
            self.on_ground = True
            if self.change_y < 0.0:
                self.change_y = 0.0

        return self.on_ground

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
        """Checks whether there is room above the obstacle to perform a basic jump."""
        if self.world is None:
            return False

        for step in range(1, 4):
            probe_x = int((self.center_x + direction * (self.collision_width * 0.7 + step * TILE_SIZE)) // TILE_SIZE)
            probe_y = int((self.center_y + self.collision_height * 0.5 + 8.0) // TILE_SIZE)
            block_id = self.world.get_block(probe_x, probe_y, generate_if_missing=False)
            if block_id != AIR and is_block_solid(block_id):
                return False
        return True

    def _update_wander_behavior(self, delta_time: float):
        """Default wander AI: move in one direction, jump over obstacles, and turn around at walls."""
        if self.jump_cooldown > 0.0:
            self.jump_cooldown = max(0.0, self.jump_cooldown - delta_time)

        self.facing_right = self.walk_direction >= 0

        if self.on_ground and self._has_wall_in_front(self.walk_direction):
            if self.jump_cooldown <= 0.0 and self._can_jump_over_obstacle(self.walk_direction):
                self.change_y = self.jump_strength
                self.change_x = self.walk_direction * self.speed * 0.8
                self.on_ground = False
                self.jump_cooldown = 0.45
                return

            self.walk_direction *= -1
            self.change_x = self.walk_direction * self.speed * 0.6
            self.jump_cooldown = max(self.jump_cooldown, 0.15)
            return

        self.change_x = self.walk_direction * self.speed * 0.75

    def update_ai(self, delta_time: float, player):
        """Default AI is passive wandering. Aggressive mobs override this method."""
        if not self.alive:
            return

        if self.stun_timer > 0.0:
            self.stun_timer = max(0.0, self.stun_timer - delta_time)
            self.change_x *= 0.9
            return

        if self.aggro_timer > 0.0:
            self.aggro_timer = max(0.0, self.aggro_timer - delta_time)

        self._update_wander_behavior(delta_time)
        self.alerted = False

    def update(self, delta_time: float, player=None):
        """Default mob update: AI -> physics -> animation."""
        if player is not None:
            self.update_ai(delta_time, player)
        self.apply_physics(delta_time)
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


class Monster(Mob):
    """A mob that can detect, chase, and damage the player."""

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
        super().__init__(world, x=x, y=y, health=health, speed=speed)
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

        self.contact_cooldown = max(0.0, self.contact_cooldown - delta_time)
        if self.contact_cooldown > 0.0:
            return

        dx = abs(player.center_x - self.center_x)
        dy = abs(player.center_y - self.center_y)
        if dx < (player.width * 0.65 + self.width * 0.65) and dy < (player.height * 0.65 + self.height * 0.65):
            if hasattr(player, "health"):
                player.health = max(0, player.health - self.damage)
            self.contact_cooldown = 1.0


Enemy = Mob
