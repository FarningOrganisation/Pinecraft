"""Pinecraft — Milestone 3.

Dieses Projekt enthält jetzt ein einfaches Block- und Chunk-Modell mit
statischer Terrain-Erzeugung. Der Spieler bleibt weiterhin das zentrale
Bewegungselement, während die Welt als einfache, deterministische
Chunk-Struktur aufgebaut wird.
"""

import math
import random
from pathlib import Path

import arcade
from arcade.gl import geometry as gl_geometry
from arcade.future.light import Light, LightLayer

from blocks import AIR, BLOCK_TEXTURES, get_block_light_opacity, is_block_skylight_surface
from dropped_item import DroppedItem
from hotbar import Hotbar
from slime import Slime
from enemy_spawning import spawn_enemy_at
from inventory_ui import InventoryUI
from items import ITEM_TEXTURES, TORCH
from lighting import LightingSystem
from physics import AABBPhysics
from player import Player
from settings import (
    BACKGROUND_COLOR,
    CHUNK_WIDTH,
    GRAVITY,
    PLAYER_SPEED,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TILE_SIZE,
    WINDOW_TITLE,
    WORLD_HEIGHT,
)
from world import World, world_to_chunk_and_local
from world_generation import build_chunk_sprite_list


class GameWindow(arcade.Window):
    """Ein kleines Spiel-Fenster mit Spieler und generierter Welt."""

    def __init__(self):
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, WINDOW_TITLE)
        arcade.set_background_color(BACKGROUND_COLOR)
        self.world = World()
        self.player = Player(world=self.world)
        self.player_sprite_list = arcade.SpriteList()
        self.player_sprite_list.append(self.player)
        self.mining_sprite_list = arcade.SpriteList()
        self.mining_sprite_list.append(self.player.mining_animation)
        self.dropped_item_sprite_list = arcade.SpriteList()
        self.dropped_items: list[DroppedItem] = []
        self.enemy_sprite_list = arcade.SpriteList()
        self.enemies: list[Slime] = []
        self.enemy_spawn_timer = 0.0
        self.max_active_enemies = 5
        self.hotbar = Hotbar(self.player)
        self.inventory_ui = InventoryUI(self.player, SCREEN_WIDTH, SCREEN_HEIGHT)
        self.chunk_sprite_lists: dict[int, arcade.SpriteList] = {}
        self.chunk_sprite_maps: dict[int, dict[tuple[int, int], arcade.Sprite]] = {}
        self.camera = arcade.Camera2D()
        self.ui_camera = arcade.Camera2D()
        self.physics = AABBPhysics(self.world)
        self.light_layer = LightLayer(self.width, self.height)
        self.lighting = LightingSystem(self)
        self.light_layer = self.light_layer
        self.torch_light_color = self.lighting.torch_light_color
        self.player_torch_light = self.lighting.player_torch_light
        self.placed_torch_lights: dict[tuple[int, int], Light] = self.lighting.placed_torch_lights
        self.sky_shader_program = self.lighting.sky_shader_program
        self.sky_quad = self.lighting.sky_quad
        self.sun_sprite = self.lighting.sun_sprite
        self.moon_sprite = self.lighting.moon_sprite
        self.render_tile_range: tuple[int, int] | None = None
        self.frame_count = 0
        self.fps_time_accumulator = 0.0
        self.fps_frame_accumulator = 0
        self.fps_display = 0.0
        self.fps_text = arcade.Text(
            text="FPS:   0.0",
            x=20,
            y=self.height - 16,
            color=arcade.color.WHITE,
            font_size=16,
            anchor_x="left",
            anchor_y="top",
        )
        self.max_chunk_loads_per_frame = 1
        self.max_chunk_unloads_per_frame = 1
        self.visible_margin_tiles = 4
        self.render_buffer_tiles = 24
        self.left_pressed = False
        self.right_pressed = False
        self.left_mouse_down = False
        self.mouse_screen_x = 0.0
        self.mouse_screen_y = 0.0
        self.pending_mine_target: tuple[int, int] | None = None
        self.break_range = 3.5 * TILE_SIZE
        self.item_pull_radius = 4.5 * TILE_SIZE
        self.item_pickup_radius = 0.95 * TILE_SIZE
        self.day_length_seconds = 24.0 * 60.0
        self.time_of_day = 0.50
        self.sun_radius = 34
        self.moon_radius = 26
        self.celestial_size_px = 35
        ui_texture_dir = Path(__file__).resolve().parent / "assets" / "textures" / "ui"
        self.heart_full_texture = arcade.load_texture(ui_texture_dir / "heart_full.png")
        self.heart_empty_texture = arcade.load_texture(ui_texture_dir / "heart_empty.png")
        self.heart_size = 16
        self.heart_gap = 2
        self.game_over = False

    def _lerp_color(self, a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
        """Wrapper to the lighting system implementation."""
        return self.lighting.lerp_color(a, b, t)

    def _day_factor(self) -> float:
        """Wrapper to the lighting system implementation."""
        return self.lighting.day_factor()

    def _sky_color(self) -> tuple[int, int, int, int]:
        """Wrapper to the lighting system implementation."""
        return self.lighting.sky_color()

    def _is_sky_lit_air(self, tile_x: int, tile_y: int, max_scan: int = 18) -> bool:
        """Wrapper to the lighting system implementation."""
        return self.lighting.is_sky_lit_air(tile_x, tile_y, max_scan=max_scan)

    def _sky_background_blend(self) -> float:
        """Wrapper to the lighting system implementation."""
        return self.lighting.sky_background_blend()

    def _ambient_color(self) -> tuple[int, int, int]:
        """Wrapper to the lighting system implementation."""
        return self.lighting.ambient_color()

    def _draw_sky_shader(self):
        """Wrapper to the lighting system implementation."""
        self.lighting.draw_sky_shader()

    def _is_torch_equipped(self) -> bool:
        """True, wenn der aktuell ausgewählte Hotbar-Slot eine Fackel enthält."""
        held_entry = self.player.inventory.get_hotbar_item(self.player.selected_hotbar_slot)
        return held_entry == TORCH

    @staticmethod
    def _torch_light_position(tile_x: int, tile_y: int) -> tuple[float, float]:
        """Lichtpunkt für eine platzierte Fackel (oben in der Texturmitte)."""
        x = (tile_x + 0.5) * TILE_SIZE
        y = (tile_y + 1.0) * TILE_SIZE
        return x, y

    def _collect_loaded_torch_tiles(self) -> set[tuple[int, int]]:
        """Sammelt platzierte Torch-Items im sichtbaren Bereich."""
        torch_tiles: set[tuple[int, int]] = set()
        min_tile_x, max_tile_x = self._get_visible_tile_x_range(margin_tiles=10)
        min_tile_y, max_tile_y = self._get_visible_tile_range(margin_tiles=8)
        for (tile_x, tile_y), item_id in self.world.placed_items.items():
            if item_id != TORCH:
                continue
            if tile_x < min_tile_x or tile_x > max_tile_x:
                continue
            if tile_y < min_tile_y or tile_y > max_tile_y:
                continue
            torch_tiles.add((tile_x, tile_y))
        return torch_tiles

    def _draw_placed_world_items(self):
        """Zeichnet platzierte Items (z. B. Fackeln) zentriert in Blockzellen."""
        min_tile_x, max_tile_x = self._get_visible_tile_x_range(margin_tiles=2)
        min_tile_y, max_tile_y = self._get_visible_tile_range(margin_tiles=2)
        draw_size = TILE_SIZE * 0.82

        for (tile_x, tile_y), item_id in self.world.placed_items.items():
            if tile_x < min_tile_x or tile_x > max_tile_x:
                continue
            if tile_y < min_tile_y or tile_y > max_tile_y:
                continue

            texture = ITEM_TEXTURES.get(item_id)
            if texture is None:
                continue

            center_x = (tile_x + 0.5) * TILE_SIZE
            center_y = (tile_y + 0.5) * TILE_SIZE
            rect = arcade.rect.XYWH(center_x, center_y, draw_size, draw_size)
            arcade.draw_texture_rect(texture, rect, alpha=255)

    def _draw_player_health(self):
        """Zeichnet die Herzen links oberhalb der Hotbar."""
        heart_count = max(0, int(getattr(self.player, "max_health", 0)))
        if heart_count <= 0:
            return

        start_x = self.hotbar.slot_x_start
        start_y = self.hotbar.slot_y + self.hotbar.slot_size + 16
        current_health = max(0, int(getattr(self.player, "health", 0)))

        for index in range(heart_count):
            texture = self.heart_full_texture if index < current_health else self.heart_empty_texture
            rect = arcade.rect.XYWH(
                start_x + index * (self.heart_size + self.heart_gap) + self.heart_size / 2,
                start_y + self.heart_size / 2,
                self.heart_size,
                self.heart_size,
            )
            arcade.draw_texture_rect(texture, rect, alpha=255)

    def _draw_game_over_overlay(self):
        """Zeichnet einen einfachen Game-Over-Bildschirm über der Szene."""
        arcade.draw_rect_filled(
            arcade.rect.XYWH(
                self.width / 2,
                self.height / 2,
                self.width,
                self.height),
            (0, 0, 0, 180),
        )
        arcade.draw_text(
            "GAME OVER",
            self.width / 2,
            self.height / 2 + 28,
            arcade.color.WHITE,
            font_size=34,
            anchor_x="center",
            anchor_y="center",
            bold=True,
        )
        arcade.draw_text(
            "Press Enter to restart",
            self.width / 2,
            self.height / 2 - 12,
            arcade.color.WHITE,
            font_size=18,
            anchor_x="center",
            anchor_y="center",
        )

    def _enemy_under_mouse(self, screen_x: float, screen_y: float):
        """Liefert den Feind unter der Maus oder None."""
        world_x, world_y = self._screen_to_world(screen_x, screen_y)
        for enemy in reversed(self.enemies):
            left = enemy.center_x - enemy.collision_width / 2
            right = enemy.center_x + enemy.collision_width / 2
            bottom = enemy.center_y - enemy.collision_height / 2
            top = enemy.center_y + enemy.collision_height / 2
            if left <= world_x <= right and bottom <= world_y <= top:
                return enemy
        return None

    def _resolve_player_attack(self):
        """Verarbeitet die aktive Nahkampf-Hitbox gegen alle Gegner."""
        if not self.player.is_attacking:
            return

        hit_left, hit_right, hit_bottom, hit_top = self.player.get_attack_hitbox()
        hit_direction = 1 if self.player.facing_right else -1

        for enemy in self.enemies:
            if not getattr(enemy, "alive", True):
                continue

            enemy_id = id(enemy)
            if enemy_id in self.player.attack_hit_targets:
                continue

            enemy_left = enemy.center_x - enemy.collision_width / 2
            enemy_right = enemy.center_x + enemy.collision_width / 2
            enemy_bottom = enemy.center_y - enemy.collision_height / 2
            enemy_top = enemy.center_y + enemy.collision_height / 2

            if hit_right < enemy_left or hit_left > enemy_right:
                continue
            if hit_top < enemy_bottom or hit_bottom > enemy_top:
                continue

            self.player.attack_hit_targets.add(enemy_id)
            enemy.apply_knockback(hit_direction * 180.0, 120.0, stun_duration=0.35)
            killed = enemy.take_damage(self.player.attack_damage)
            if killed:
                continue

    def _sync_torch_lights(self):
        """Synchronisiert Spieler- und Welt-Fackellichter mit dem aktuellen Zustand."""
        torch_daylight_scale = self._torch_daylight_multiplier(self.player.center_x, self.player.center_y)

        if self._is_torch_equipped():
            light_pos = self.player.get_equipped_light_source_position()
            if light_pos is None:
                light_pos = (self.player.center_x, self.player.center_y + self.player.height * 0.10)
            self.player_torch_light.position = light_pos
            self.player_torch_light.radius = 150.0 * torch_daylight_scale
            self.player_torch_light.color = self.torch_light_color
        else:
            self.player_torch_light.radius = 0.0

        current_torch_tiles = self._collect_loaded_torch_tiles()
        existing_torch_tiles = set(self.placed_torch_lights.keys())

        for tile_pos in existing_torch_tiles - current_torch_tiles:
            light = self.placed_torch_lights.pop(tile_pos)
            self.light_layer.remove(light)

        for tile_pos in current_torch_tiles:
            light = self.placed_torch_lights.get(tile_pos)
            light_x, light_y = self._torch_light_position(tile_pos[0], tile_pos[1])
            tile_scale = self._torch_daylight_multiplier(light_x, light_y)
            radius = 135.0 * tile_scale
            if light is None:
                light = Light(light_x, light_y, radius=radius, color=self.torch_light_color, mode="soft")
                self.light_layer.add(light)
                self.placed_torch_lights[tile_pos] = light
            else:
                light.position = (light_x, light_y)
                light.radius = radius
                light.color = self.torch_light_color

    def _torch_daylight_multiplier(self, world_x: float, world_y: float) -> float:
        """Wrapper to the lighting system implementation."""
        return self.lighting.torch_daylight_multiplier(world_x, world_y)

    def _has_sky_access(self, world_x: float, world_y: float, max_scan: int = 18) -> bool:
        """Wrapper to the lighting system implementation."""
        return True

    def _get_visible_tile_x_range(self, margin_tiles: int = 2) -> tuple[int, int]:
        """Berechnet den horizontal sichtbaren Tile-Bereich der Kamera."""
        half_w = self.width / 2
        min_tile_x = int((self.camera.position[0] - half_w) // TILE_SIZE) - margin_tiles
        max_tile_x = int((self.camera.position[0] + half_w) // TILE_SIZE) + margin_tiles
        return min_tile_x, max_tile_x

    def _column_surface_and_shadow(self, tile_x: int) -> tuple[int, float]:
        """Wrapper to the lighting system implementation."""
        return self.lighting._column_surface_and_shadow(tile_x)

    def _torch_shadow_positions(self) -> list[tuple[int, int]]:
        """Wrapper to the lighting system implementation."""
        return self.lighting._torch_shadow_positions()

    def _compute_connected_sky_light(
        self,
        min_tile_x: int,
        max_tile_x: int,
        min_tile_y: int,
        max_tile_y: int,
    ) -> dict[tuple[int, int], float]:
        """Wrapper to the lighting system implementation."""
        return self.lighting._compute_connected_sky_light(min_tile_x, max_tile_x, min_tile_y, max_tile_y)

    def _draw_underground_darkness_overlay(self):
        """Wrapper to the lighting system implementation."""
        self.lighting.draw_underground_darkness_overlay()

    def _celestial_position(self, progress: float) -> tuple[float, float]:
        """Wrapper to the lighting system implementation."""
        p = max(0.0, min(1.0, progress))
        theta = math.pi * p
        center_x = self.width * 0.5
        center_y = self.height / 3.0
        radius_x = self.width * 0.62
        radius_y = self.height * 0.64
        x = center_x + radius_x * math.cos(theta)
        y = center_y + radius_y * math.sin(theta)
        return x, y

    @staticmethod
    def _draw_glow_orb(
        x: float,
        y: float,
        core_radius: float,
        glow_color: tuple[int, int, int],
        strength: float,
    ):
        """Wrapper to the lighting system implementation."""
        LightingSystem.draw_glow_orb(x, y, core_radius, glow_color, strength)

    def _draw_celestials(self):
        """Wrapper to the lighting system implementation."""
        self.lighting.draw_celestials()

    def _spawn_dropped_item(self, entry_id: int, tile_x: int, tile_y: int):
        """Erzeugt ein physisches Item an der Blockposition."""
        texture = self.player.inventory.get_texture(entry_id)
        if texture is None:
            return

        spawn_x, spawn_y = self.world.to_world_position(tile_x, tile_y)
        drop = DroppedItem(entry_id=entry_id, texture=texture, spawn_x=spawn_x, spawn_y=spawn_y)
        self.dropped_items.append(drop)
        self.dropped_item_sprite_list.append(drop.sprite)

    def _update_dropped_items(self, delta_time: float):
        """Aktualisiert Drop-Physik und sammelt erreichbare Items auf."""
        if not self.dropped_items:
            return

        preferred_slot = self.player.inventory.HOTBAR_START + self.player.selected_hotbar_slot
        physics_delta = min(delta_time, 1 / 30)

        remaining: list[DroppedItem] = []
        for drop in self.dropped_items:
            wants_pickup = drop.update(
                world=self.world,
                player=self.player,
                delta_time=physics_delta,
                gravity=GRAVITY,
                pull_radius=self.item_pull_radius,
                pickup_radius=self.item_pickup_radius,
            )

            if wants_pickup:
                left = self.player.inventory.add_item(drop.entry_id, 1, preferred_slot_index=preferred_slot)
                if left <= 0:
                    self.dropped_item_sprite_list.remove(drop.sprite)
                    continue

            remaining.append(drop)

        self.dropped_items = remaining

    def _clamped_camera_position(self):
        """Klemmt die Kamera, damit man nicht unter die Welt schauen kann."""
        min_camera_y = self.height / 2
        camera_y = max(self.player.center_y, min_camera_y)
        return self.player.center_x, camera_y

    def _rebuild_world_sprites(self):
        """Erzeugt den Chunk-Sprite-Cache für den aktuellen Sichtbereich neu."""
        min_tile_y, max_tile_y = self._get_target_render_tile_range()
        self.chunk_sprite_lists = {}
        self.chunk_sprite_maps = {}
        for chunk_x in sorted(self.world.chunks):
            chunk = self.world.chunks[chunk_x]
            sprite_list, sprite_map = build_chunk_sprite_list(chunk_x, chunk, min_tile_y, max_tile_y)
            self.chunk_sprite_lists[chunk_x] = sprite_list
            self.chunk_sprite_maps[chunk_x] = sprite_map
        self.render_tile_range = (min_tile_y, max_tile_y)

    def _get_visible_tile_range(self, margin_tiles: int | None = None) -> tuple[int, int]:
        """Berechnet den vertikal sichtbaren Tile-Bereich der Kamera."""
        if margin_tiles is None:
            margin_tiles = self.visible_margin_tiles
        half_h = self.height / 2
        min_tile_y = max(0, int((self.camera.position[1] - half_h) // TILE_SIZE) - margin_tiles)
        max_tile_y = int((self.camera.position[1] + half_h) // TILE_SIZE) + margin_tiles
        return min_tile_y, max_tile_y

    def _get_target_render_tile_range(self) -> tuple[int, int]:
        """Sichtbereich plus Puffer, um häufige Rebuilds beim Springen zu vermeiden."""
        visible_min, visible_max = self._get_visible_tile_range()
        return (
            max(0, visible_min - self.render_buffer_tiles),
            visible_max + self.render_buffer_tiles,
        )

    def _get_visible_chunk_range(self, margin_chunks: int = 1) -> tuple[int, int]:
        """Berechnet den horizontal sichtbaren Chunk-Bereich der Kamera."""
        half_w = self.width / 2
        left_x = self.camera.position[0] - half_w - margin_chunks * CHUNK_WIDTH * TILE_SIZE
        right_x = self.camera.position[0] + half_w + margin_chunks * CHUNK_WIDTH * TILE_SIZE
        min_tile_x = int(left_x // TILE_SIZE)
        max_tile_x = int(right_x // TILE_SIZE)
        min_chunk_x, _ = world_to_chunk_and_local(min_tile_x)
        max_chunk_x, _ = world_to_chunk_and_local(max_tile_x)
        return min_chunk_x, max_chunk_x

    def _sync_chunk_sprite_cache(self, loaded_chunks: list[int], unloaded_chunks: list[int]):
        """Aktualisiert nur die geänderten Chunk-Sprites."""
        for chunk_x in unloaded_chunks:
            self.chunk_sprite_lists.pop(chunk_x, None)
            self.chunk_sprite_maps.pop(chunk_x, None)

        if not loaded_chunks:
            return

        if self.render_tile_range is None:
            min_tile_y, max_tile_y = self._get_target_render_tile_range()
            self.render_tile_range = (min_tile_y, max_tile_y)
        else:
            min_tile_y, max_tile_y = self.render_tile_range

        for chunk_x in loaded_chunks:
            chunk = self.world.chunks.get(chunk_x)
            if chunk is None:
                continue
            sprite_list, sprite_map = build_chunk_sprite_list(chunk_x, chunk, min_tile_y, max_tile_y)
            self.chunk_sprite_lists[chunk_x] = sprite_list
            self.chunk_sprite_maps[chunk_x] = sprite_map

    def _apply_world_block_diffs(self, changes: list[tuple[int, int, int, int]]):
        """Aktualisiert Sprites einzelner geänderter Blöcke ohne Chunk-Rebuild."""
        if not changes:
            return

        if self.render_tile_range is None:
            min_tile_y, max_tile_y = self._get_target_render_tile_range()
            self.render_tile_range = (min_tile_y, max_tile_y)
        else:
            min_tile_y, max_tile_y = self.render_tile_range

        for tile_x, tile_y, _old_block_id, new_block_id in changes:
            chunk_x, local_x = world_to_chunk_and_local(tile_x)
            sprite_list = self.chunk_sprite_lists.get(chunk_x)
            if sprite_list is None:
                continue

            sprite_map = self.chunk_sprite_maps.setdefault(chunk_x, {})
            key = (local_x, tile_y)
            existing_sprite = sprite_map.get(key)

            in_visible_band = min_tile_y <= tile_y <= max_tile_y
            texture = BLOCK_TEXTURES.get(new_block_id)
            should_render = in_visible_band and new_block_id != AIR and texture is not None

            if existing_sprite is not None and not should_render:
                sprite_list.remove(existing_sprite)
                sprite_map.pop(key, None)
                continue

            if not should_render:
                continue

            if texture is None:
                continue

            if existing_sprite is not None:
                existing_sprite.texture = texture
                continue

            sprite = arcade.Sprite(texture)
            sprite.center_x = (chunk_x * self.world.chunks[chunk_x].width + local_x + 0.5) * TILE_SIZE
            sprite.center_y = (tile_y + 0.5) * TILE_SIZE
            sprite.width = TILE_SIZE
            sprite.height = TILE_SIZE
            sprite_list.append(sprite)
            sprite_map[key] = sprite

    def _get_local_blocks(self, left: float, right: float, bottom: float, top: float):
        """Gibt nur die relevanten Blöcke um den Spieler zurück."""
        for tile_x, tile_y, block_left, block_right, block_bottom, block_top in self.world.get_blocks_around(
            left, right, bottom, top
        ):
            yield tile_x, tile_y, block_left, block_right, block_bottom, block_top

    def setup(self):
        """Initialisiert den Spielzustand."""
        self.game_over = False
        self.frame_count = 0
        self.world = World()
        self.player = Player(world=self.world)
        self.player.center_x = SCREEN_WIDTH / 2
        ground_y = self.world.get_ground_top(int(self.player.center_x))
        self.player.center_y = ground_y + self.player.height / 2
        self.player.change_x = 0.0
        self.player.change_y = 0.0
        self.player.on_ground = True
        self.player.health = max(1, getattr(self.player, "max_health", 10))
        self.player_sprite_list = arcade.SpriteList()
        self.player_sprite_list.append(self.player)
        self.mining_sprite_list = arcade.SpriteList()
        self.mining_sprite_list.append(self.player.mining_animation)
        self.dropped_item_sprite_list = arcade.SpriteList()
        self.dropped_items = []
        self.enemy_sprite_list = arcade.SpriteList()
        self.enemies = []
        self.enemy_spawn_timer = 0.0
        self.hotbar = Hotbar(self.player)
        self.inventory_ui = InventoryUI(self.player, SCREEN_WIDTH, SCREEN_HEIGHT)
        self.physics = AABBPhysics(self.world)
        for light in list(self.light_layer):
            self.light_layer.remove(light)
        self.player_torch_light = Light(0.0, 0.0, radius=0.0, color=(255, 255, 230), mode="soft")
        self.light_layer.add(self.player_torch_light)
        self.placed_torch_lights = {}
        self.chunk_sprite_lists = {}
        self.chunk_sprite_maps = {}
        self.render_tile_range = None
        self.camera.position = self._clamped_camera_position()
        self.world.update_loaded_chunks(self.player.center_x)
        self._rebuild_world_sprites()
        self.light_layer.resize(self.width, self.height)
        self._sync_torch_lights()

    def spawn_enemy(self, enemy_class, x: float, y: float, **enemy_kwargs):
        """Spawns any enemy class at the requested world position."""
        if len(self.enemies) >= self.max_active_enemies:
            print("[enemy-spawn] skipped: max enemy count reached")
            return None

        return spawn_enemy_at(
            self.world,
            enemy_class,
            self.enemies,
            self.enemy_sprite_list,
            x=x,
            y=y,
            **enemy_kwargs,
        )

    def on_update(self, delta_time: float):
        """Wird regelmäßig pro Frame aufgerufen."""
        if self.game_over:
            return

        self.frame_count += 1
        if self.day_length_seconds > 0:
            self.time_of_day = (self.time_of_day + delta_time / self.day_length_seconds) % 1.0

        self.fps_time_accumulator += delta_time
        self.fps_frame_accumulator += 1
        if self.fps_time_accumulator >= 0.25:
            self.fps_display = self.fps_frame_accumulator / self.fps_time_accumulator
            self.fps_time_accumulator = 0.0
            self.fps_frame_accumulator = 0
            self.fps_text.text = f"FPS: {self.fps_display:5.1f}"

        if self.left_pressed and not self.right_pressed:
            self.player.move_left()
        elif self.right_pressed and not self.left_pressed:
            self.player.move_right()
        elif self.player.on_ground:
            self.player.stop_horizontal()

        was_on_ground = self.player.on_ground
        physics_delta = min(delta_time, 1 / 30)
        self.physics.update(self.player, physics_delta)
        if was_on_ground and not self.player.on_ground:
            self.player.begin_fall_tracking()
        elif not was_on_ground and self.player.on_ground:
            self.player.apply_fall_damage()
        self.player.update(physics_delta)

        if self.left_mouse_down and not self.inventory_ui.visible:
            target = self._get_block_from_mouse(self.mouse_screen_x, self.mouse_screen_y)
            if target is not None and not self.player.is_mining:
                tile_x, tile_y, _ = target
                self.pending_mine_target = (tile_x, tile_y)
                self.player.start_mining((tile_x, tile_y))

        if self.pending_mine_target is not None and not self.inventory_ui.visible and not self.player.is_mining:
            target_x, target_y = self.pending_mine_target
            block_id = self.world.get_block(target_x, target_y)
            if block_id != AIR:
                self.player.start_mining((target_x, target_y))
            self.pending_mine_target = None

        for drop_id, tile_x, tile_y in self.player.consume_pending_item_drops():
            self._spawn_dropped_item(drop_id, tile_x, tile_y)
        self._update_dropped_items(physics_delta)

        if self.player.mining_target is not None:
            tile_x, tile_y = self.player.mining_target
            world_x, world_y = self.world.to_world_position(tile_x, tile_y)
            self.player.mining_animation.center_x = world_x
            self.player.mining_animation.center_y = world_y
            self.player.mining_animation.visible = True
        else:
            self.player.mining_animation.visible = False

        self._resolve_player_attack()

        self.camera.position = self._clamped_camera_position()

        visible_range = self._get_visible_tile_range()
        did_full_rebuild = False
        if self.render_tile_range is None:
            self._rebuild_world_sprites()
            did_full_rebuild = True
        else:
            render_min, render_max = self.render_tile_range
            visible_min, visible_max = visible_range
            if visible_min < render_min or visible_max > render_max:
                self._rebuild_world_sprites()
                did_full_rebuild = True

        block_changes = self.world.consume_changed_blocks()
        if block_changes and not did_full_rebuild:
            self._apply_world_block_diffs(block_changes)

        if self.player.world_dirty:
            self.player.world_dirty = False
            self.player.dirty_chunk_xs.clear()

        loaded_chunks, unloaded_chunks = self.world.update_loaded_chunks(
            self.player.center_x,
            max_loads=self.max_chunk_loads_per_frame,
            max_unloads=self.max_chunk_unloads_per_frame,
        )
        if loaded_chunks or unloaded_chunks:
            self._sync_chunk_sprite_cache(loaded_chunks, unloaded_chunks)

        self._sync_torch_lights()
        self._update_enemies(delta_time)

        if self.player.health <= 0:
            self.player.health = 0
            self.game_over = True

    def _screen_to_world(self, screen_x: float, screen_y: float):
        """Konvertiert Bildschirmkoordinaten in Weltkoordinaten."""
        world_x = self.camera.position[0] + (screen_x - self.width / 2)
        world_y = self.camera.position[1] + (screen_y - self.height / 2)
        return world_x, world_y

    def _get_block_from_mouse(self, screen_x: float, screen_y: float):
        """Gibt den Block unter der Maus in Weltkoordinaten zurück oder None."""
        world_x, world_y = self._screen_to_world(screen_x, screen_y)
        tile_x, tile_y = self.world.to_block_position(world_x, world_y)
        block_id = self.world.get_block(tile_x, tile_y)
        if block_id == AIR:
            return None

        block_center_x, block_center_y = self.world.to_world_position(tile_x, tile_y)
        distance = ((block_center_x - self.player.center_x) ** 2 + (block_center_y - self.player.center_y) ** 2) ** 0.5
        if distance > self.break_range:
            return None

        return tile_x, tile_y, block_id

    def _get_placed_item_from_mouse(self, screen_x: float, screen_y: float):
        """Gibt ein platziertes Item unter der Maus zurück oder None."""
        world_x, world_y = self._screen_to_world(screen_x, screen_y)
        tile_x, tile_y = self.world.to_block_position(world_x, world_y)
        item_id = self.world.get_placed_item(tile_x, tile_y)
        if item_id is None:
            return None

        item_center_x, item_center_y = self.world.to_world_position(tile_x, tile_y)
        distance = ((item_center_x - self.player.center_x) ** 2 + (item_center_y - self.player.center_y) ** 2) ** 0.5
        if distance > self.break_range:
            return None

        return tile_x, tile_y, item_id

    def _can_spawn_enemy_at(self, world_x: float, world_y: float, ignore_player_distance: bool = False) -> bool:
        """Prüft, ob an dieser Position ein Slime zuverlässig spawnen darf."""
        tile_x = int(world_x // TILE_SIZE)
        tile_y = int(world_y // TILE_SIZE)
        if tile_y < 1 or tile_y >= 220:
            return False
        if self.world.get_block(tile_x, tile_y, generate_if_missing=False) != 0:
            return False
        if self.world.get_block(tile_x, tile_y - 1, generate_if_missing=False) == 0:
            return False

        if not ignore_player_distance and abs(world_x - self.player.center_x) < 600.0:
            return False

        for (torch_x, torch_y), item_id in self.world.placed_items.items():
            if item_id != TORCH:
                continue
            light_x = (torch_x + 0.5) * TILE_SIZE
            light_y = (torch_y + 1.0) * TILE_SIZE
            if math.hypot(world_x - light_x, world_y - light_y) < 180.0:
                return False

        if self._day_factor() > 0.45:
            world_surface = self.world.get_surface_height(tile_x)
            if world_surface >= tile_y - 1:
                return False
        return True

    def _spawn_test_slime(self):
        """Spawns exactly one test slime next to the player on demand."""
        self.spawn_enemy(Slime, self.player.center_x + 96.0, self.player.center_y + 32.0)

        slime = self.enemies[-1]
        spawn_tile_x = int(slime.center_x // TILE_SIZE)
        ground_y = self.world.get_ground_top(spawn_tile_x)
        slime.center_y = ground_y + slime.height / 2
        slime.on_ground = True
        slime.change_x = 0.0
        slime.change_y = 0.0
        slime.jump_cooldown = 0.0
        print(
            f"[enemy-spawn-ground] {slime.__class__.__name__} "
            f"x={slime.center_x:.1f} y={slime.center_y:.1f} "
            f"ground_y={ground_y:.1f}"
        )

    def _spawn_enemy_if_needed(self):
        """Spawns normal roaming enemies if the timer allows it."""
        if len(self.enemies) >= self.max_active_enemies:
            return
        if self.enemy_spawn_timer > 0.0:
            return

        for _ in range(18):
            angle = random.uniform(0.0, 2.0 * math.pi)
            distance = random.uniform(700.0, 1800.0)
            spawn_x = self.player.center_x + math.cos(angle) * distance
            spawn_tile_x = int(spawn_x // TILE_SIZE)
            ground_y = self.world.get_ground_top(spawn_tile_x)
            spawn_y = ground_y + 14.0

            if not self._can_spawn_enemy_at(spawn_x, spawn_y):
                continue

            slime = Slime(self.world, x=spawn_x, y=spawn_y)
            self.enemies.append(slime)
            self.enemy_sprite_list.append(slime)
            self.enemy_spawn_timer = 3.0
            return

    def _update_enemies(self, delta_time: float):
        """Aktualisiert alle Feinde und entfernt tote Feinde aus der Liste."""
        alive_enemies: list[Slime] = []
        for enemy in self.enemies:
            if not getattr(enemy, "alive", True):
                self.enemy_sprite_list.remove(enemy)
                continue

            enemy.update_ai(delta_time, self.player)
            if enemy.health <= 0 or enemy.center_y < -64:
                self.enemy_sprite_list.remove(enemy)
                continue
            alive_enemies.append(enemy)

        self.enemies = alive_enemies
        self.enemy_spawn_timer = max(0.0, self.enemy_spawn_timer - delta_time)
        self._spawn_enemy_if_needed()

    def on_draw(self):
        """Zeichnet die Szene und die Minecraft-artige Hotbar."""
        self.clear((0, 0, 0, 255))

        self.camera.use()

        with self.light_layer:
            self._draw_sky_shader()

            self.ui_camera.use()
            self._draw_celestials()

            self.camera.use()
            min_chunk_x, max_chunk_x = self._get_visible_chunk_range()
            for chunk_x in range(min_chunk_x, max_chunk_x + 1):
                chunk_sprites = self.chunk_sprite_lists.get(chunk_x)
                if chunk_sprites is not None:
                    chunk_sprites.draw()
            self._draw_placed_world_items()
            self.dropped_item_sprite_list.draw()
            self.enemy_sprite_list.draw()
            self.player.draw_held_item(layer="back")
            self.player_sprite_list.draw()
            self.player.draw_held_item(layer="front")
            self.player.draw_attack_animation()
            self.mining_sprite_list.draw()
            self._draw_underground_darkness_overlay()

        self.light_layer.draw(ambient_color=self._ambient_color())

        self.ui_camera.use()
        self._draw_player_health()
        self.hotbar.draw()
        self.inventory_ui.draw()
        self.fps_text.y = self.height - 16
        self.fps_text.draw()

        if self.game_over:
            self._draw_game_over_overlay()

    def on_key_press(self, symbol: int, modifiers: int):
        """Reagiert auf Tastatureingaben."""
        if self.game_over:
            if symbol == arcade.key.ENTER:
                self.setup()
            return

        cmd_down = bool(modifiers & arcade.key.MOD_COMMAND)
        if cmd_down and symbol == arcade.key.D:
            self.time_of_day = 0.50
            return

        if cmd_down and symbol == arcade.key.LEFT:
            self.time_of_day = (self.time_of_day + 0.02) % 1.0
            return

        if cmd_down and symbol == arcade.key.RIGHT:
            self.time_of_day = (self.time_of_day - 0.02) % 1.0
            return

        if cmd_down and symbol == arcade.key.N:
            self.time_of_day = 0.00
            return

        if symbol == arcade.key.P:
            self._spawn_test_slime()
            return

        if 49 <= symbol <= 57:
            slot_index = symbol - 49
            self.player.select_hotbar_slot(slot_index)
            return

        if symbol in (arcade.key.A, arcade.key.LEFT):
            self.left_pressed = True
            self.player.move_left()
        elif symbol in (arcade.key.D, arcade.key.RIGHT):
            self.right_pressed = True
            self.player.move_right()
        elif symbol == arcade.key.SPACE or symbol == arcade.key.UP or symbol == arcade.key.W:
            if self.player.on_ground:
                self.player.jump()
        elif symbol == arcade.key.E:
            self.inventory_ui.toggle()

    def on_key_release(self, symbol: int, modifiers: int):
        """Stoppt die Bewegung bei Tastenloslassen."""
        if symbol in (arcade.key.A, arcade.key.LEFT):
            self.left_pressed = False
        elif symbol in (arcade.key.D, arcade.key.RIGHT):
            self.right_pressed = False

        if not self.left_pressed and not self.right_pressed:
            self.player.stop_horizontal()
        elif self.left_pressed and not self.right_pressed:
            self.player.move_left()
        elif self.right_pressed and not self.left_pressed:
            self.player.move_right()

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        """Verarbeitet Links- und Rechtsklicks für Abbauen, Platzieren und Inventar-Interaktion."""
        if self.game_over:
            return

        self.mouse_screen_x = x
        self.mouse_screen_y = y

        if self.inventory_ui.visible:
            self.inventory_ui.handle_click(x, y, button, modifiers)
            return

        if button == arcade.MOUSE_BUTTON_LEFT:
            enemy = self._enemy_under_mouse(x, y)
            if enemy is not None:
                self.left_mouse_down = False
                self.pending_mine_target = None
                self.player.start_attack()
                return

            placed_item = self._get_placed_item_from_mouse(x, y)
            if placed_item is not None:
                tile_x, tile_y, item_id = placed_item
                removed_item = self.world.remove_placed_item(tile_x, tile_y)
                if removed_item is not None:
                    self.player.inventory.add_item(removed_item, 1)
                return

            target = self._get_block_from_mouse(x, y)
            if target is None:
                self.left_mouse_down = False
                self.pending_mine_target = None
                self.player.start_attack()
                return

            self.left_mouse_down = True
            tile_x, tile_y, _ = target
            self.pending_mine_target = (tile_x, tile_y)
            self.player.start_mining((tile_x, tile_y))

            if self.player.is_mining:
                self.pending_mine_target = None
            return

        if button == arcade.MOUSE_BUTTON_RIGHT:
            world_x, world_y = self._screen_to_world(x, y)
            tile_x, tile_y = self.world.to_block_position(world_x, world_y)
            self.player.place_selected_block(self.world, tile_x, tile_y)

    def on_mouse_release(self, x: float, y: float, button: int, modifiers: int):
        """Aktualisiert den Maustastenstatus und bricht Mining auf Wunsch ab."""
        self.mouse_screen_x = x
        self.mouse_screen_y = y
        if button == arcade.MOUSE_BUTTON_LEFT:
            self.left_mouse_down = False
            self.pending_mine_target = None
            self.player.cancel_mining()

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float):
        """Merkt die letzte Mausposition für Hold-to-Mine."""
        self.mouse_screen_x = x
        self.mouse_screen_y = y

    def on_mouse_drag(self, x: float, y: float, dx: float, dy: float, buttons: int, modifiers: int):
        """Merkt die letzte Mausposition auch beim Ziehen."""
        self.mouse_screen_x = x
        self.mouse_screen_y = y


def main():
    """Startet die Spielschleife."""
    window = GameWindow()
    window.setup()
    arcade.run()


if __name__ == "__main__":
    main()
