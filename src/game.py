"""Pinecraft — Milestone 3.

Dieses Projekt enthält jetzt ein einfaches Block- und Chunk-Modell mit
statischer Terrain-Erzeugung. Der Spieler bleibt weiterhin das zentrale
Bewegungselement, während die Welt als einfache, deterministische
Chunk-Struktur aufgebaut wird.
"""

import math
import random
import signal
import atexit
import importlib
from pathlib import Path
from typing import Any, cast

import arcade
import arcade.gui
from arcade.future.light import Light, LightLayer

from blocks import AIR, BLOCK_TEXTURES, get_block_light_opacity, is_block_skylight_surface, is_block_solid
from dropped_item import DroppedItem
from items import ITEM_TEXTURES, TORCH
from mobs.mob_spawning import spawn_mob_at, spawn_mob_next_to_player
from mobs.mob import Mob
from mobs.chicken import Chicken
from mobs.slime import Slime
from mobs.zombie import Zombie
from lighting import LightingSystem
from physics import AABBPhysics, aabb_overlap
from player import Player
from ui.bubble_ui import BubbleUI
from ui.health_ui import HealthUI
from ui.hotbar import Hotbar
from ui.inventory_ui import InventoryUI
from game_menu_view import GameMenuView
from settings import (
    BACKGROUND_COLOR,
    CHUNK_WIDTH,
    GRAVITY,
    PLAYER_SPEED,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    START_FULLSCREEN,
    TILE_SIZE,
    WINDOW_TITLE,
    WORLD_SEED,
    WORLD_HEIGHT,
)
from world import World, world_to_chunk_and_local
from world_generation import (
    LAVA_RENDER_THRESHOLD,
    LAVA_TEXTURE,
    LAVA_VISUAL_STEPS,
    WATER_VISUAL_STEPS,
    WATER_RENDER_THRESHOLD,
    WATER_TEXTURE,
    build_chunk_lava_sprite_list,
    build_chunk_sprite_list,
    build_chunk_water_sprite_list,
    get_lava_render_height,
    get_water_render_height,
)
from save_system import load_save, save_game

# Choose the mob type spawned via the debug key from here instead of scrolling down.
DEBUG_SPAWN_MOB_CLASS = Slime


class GameView(arcade.View):
    """Ein kleines Spiel-Fenster mit Spieler und generierter Welt."""

    def __init__(
        self,
        seed: int | None = None,
        world_name: str = "World",
        save_data: dict | None = None,
        restore_runtime_state: bool = False,
    ):
        super().__init__()
        arcade.set_background_color(BACKGROUND_COLOR)
        self.world_name = world_name or "World"
        self.start_world_seed = WORLD_SEED if seed is None else seed
        self._pending_save_data = save_data
        self._restore_runtime_state = bool(restore_runtime_state)
        self.start_fullscreen = START_FULLSCREEN
        self.show_start_menu = False
        self.start_menu_seed_text = str(self.start_world_seed)
        self.world = World()
        self.player = Player(world=self.world)
        self.player_sprite_list = arcade.SpriteList()
        self.player_sprite_list.append(self.player)
        self.mining_sprite_list = arcade.SpriteList()
        self.mining_sprite_list.append(self.player.mining_animation)
        self.dropped_item_sprite_list = arcade.SpriteList()
        self.dropped_items: list[DroppedItem] = []
        self.mob_sprite_list = arcade.SpriteList()
        self.mobs: list[Mob] = []
        self.mob_spawn_timer = 0.0
        self.max_active_mobs = 5
        self.hotbar = Hotbar(self.player)
        self.health_ui = HealthUI(self.player, self.hotbar)
        self.bubble_ui = BubbleUI(self.player, self.hotbar, self.health_ui)
        self.inventory_ui = InventoryUI(self.player, SCREEN_WIDTH, SCREEN_HEIGHT)
        self.ui_manager = arcade.gui.UIManager()
        self.inventory_anchor = arcade.gui.UIAnchorLayout(size_hint=(1.0, 1.0))
        self.ui_manager.add(self.bubble_ui)
        self.ui_manager.add(self.hotbar)
        self.ui_manager.add(self.health_ui)
        self.ui_manager.add(self.inventory_anchor)
        self.inventory_anchor.add(self.inventory_ui, anchor_x="center", anchor_y="center")
        self.chunk_sprite_lists: dict[int, arcade.SpriteList] = {}
        self.chunk_sprite_maps: dict[int, dict[tuple[int, int], arcade.Sprite]] = {}
        self.water_sprite_list = arcade.SpriteList()
        self.water_sprite_maps: dict[int, dict[tuple[int, int], arcade.Sprite]] = {}
        self.lava_sprite_list = arcade.SpriteList()
        self.lava_sprite_maps: dict[int, dict[tuple[int, int], arcade.Sprite]] = {}
        self._debug_logged_tiny_edge_cells: set[tuple[int, int]] = set()
        self.camera = arcade.Camera2D()
        self.ui_camera = arcade.Camera2D()
        self.physics = AABBPhysics(self.world)
        self.light_layer: LightLayer | None = None
        self.lighting: LightingSystem | None = None
        self.torch_light_color = (255, 190, 100)
        self.lava_light_color = (255, 122, 68)
        self.player_torch_light: Light | None = None
        self.placed_torch_lights: dict[tuple[int, int], Light] = {}
        self.sampled_lava_lights: dict[tuple[int, int], Light] = {}
        self.sky_shader_program = None
        self.sky_quad = None
        self.sun_sprite = None
        self.moon_sprite = None
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
        self.jump_pressed = False
        self.left_mouse_held = False
        self.left_mouse_mining_chain = False
        self.mouse_screen_x = 0.0
        self.mouse_screen_y = 0.0
        self.break_range = 3.5 * TILE_SIZE
        self.item_pull_radius = 4.5 * TILE_SIZE
        self.item_pickup_radius = 0.95 * TILE_SIZE
        self.item_throw_speed = 280.0
        self.item_throw_upward_speed = 55.0
        self.item_throw_spawn_distance = TILE_SIZE * 1.45
        self.item_throw_pickup_delay = 0.9
        self.day_length_seconds = 24.0 * 60.0
        self.time_of_day = 0.50
        self.sun_radius = 34
        self.moon_radius = 26
        self.celestial_size_px = 35
        self.game_over = False
        self._game_over_resume_bounds: tuple[float, float, float, float] | None = None
        self._game_over_menu_bounds: tuple[float, float, float, float] | None = None
        self._runtime_initialized = False

    def _build_restore_overlay_view(self, view_key: str, owner_view: arcade.View | None = None) -> arcade.View | None:
        """Erzeugt eine Overlay-View fuer den Dev-Restore, falls moeglich."""
        key = (view_key or "").strip()
        if not key:
            return None
        if key == "game_menu":
            return GameMenuView(self)
        if ":" not in key:
            return None

        module_name, class_name = key.split(":", 1)
        try:
            module = importlib.import_module(module_name)
            view_class = getattr(module, class_name)
        except Exception:
            return None

        if not isinstance(view_class, type) or not issubclass(view_class, arcade.View):
            return None

        candidates: list[arcade.View] = []
        if owner_view is not None:
            candidates.append(owner_view)
        candidates.append(self)

        view: arcade.View | None = None
        for owner in candidates:
            try:
                created = cast(Any, view_class)(owner)
            except Exception:
                continue
            if isinstance(created, arcade.View):
                view = created
                break

        if view is None:
            return None

        return view

    def _initialize_runtime(self):
        """Initialisiert GL-abhängige Systeme erst mit aktivem Fenster."""
        if self._runtime_initialized:
            return
        if self.window is None:
            return

        self.light_layer = LightLayer(int(self.window.width), int(self.window.height))
        self.lighting = LightingSystem(self)
        self.torch_light_color = self.lighting.torch_light_color
        self.player_torch_light = self.lighting.player_torch_light
        self.placed_torch_lights = self.lighting.placed_torch_lights
        self.sky_shader_program = self.lighting.sky_shader_program
        self.sky_quad = self.lighting.sky_quad
        self.sun_sprite = self.lighting.sun_sprite
        self.moon_sprite = self.lighting.moon_sprite
        self._runtime_initialized = True
        self.setup(seed_override=self.start_world_seed)

    def on_show_view(self):
        """Aktiviert UI-Systeme, wenn die View sichtbar wird."""
        self._initialize_runtime()
        self.ui_manager.enable()
        if self.window is not None:
            # Diese View kann versteckt gewesen sein, waehrend Fullscreen umgeschaltet wurde.
            self.on_resize(int(self.window.width), int(self.window.height))
        # Verhindert haengende Bewegungszustände nach View-Wechseln.
        self.left_pressed = False
        self.right_pressed = False
        self.jump_pressed = False
        if hasattr(self, "player") and self.player is not None:
            self.player.stop_horizontal()

    def on_hide_view(self):
        """Deaktiviert UI-Systeme, wenn die View ausgeblendet wird."""
        self.ui_manager.disable()

    @property
    def ctx(self):
        """Kompatibilitaet: LightingSystem nutzt self.ctx wie zuvor beim Window."""
        if self.window is None:
            raise RuntimeError("GameView has no window context yet")
        return self.window.ctx

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
        """Lichtpunkt für eine platzierte Fackel (Zentrum der Blockzelle)."""
        x = (tile_x + 0.5) * TILE_SIZE
        y = (tile_y + 0.5) * TILE_SIZE
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

    def _draw_game_over_overlay(self):
        """Zeichnet einen Game-Over-Bildschirm mit Resume/Menu-Buttons."""
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
            self.height / 2 + 84,
            arcade.color.WHITE,
            font_size=34,
            anchor_x="center",
            anchor_y="center",
            bold=True,
        )

        arcade.draw_text(
            "You dropped your inventory",
            self.width / 2,
            self.height / 2 + 48,
            arcade.color.LIGHT_GRAY,
            font_size=16,
            anchor_x="center",
            anchor_y="center",
        )

        button_w = 280.0
        button_h = 44.0
        resume_cx = self.width / 2
        resume_cy = self.height / 2 - 2
        menu_cx = self.width / 2
        menu_cy = self.height / 2 - 60

        self._game_over_resume_bounds = (
            resume_cx - button_w / 2,
            resume_cx + button_w / 2,
            resume_cy - button_h / 2,
            resume_cy + button_h / 2,
        )
        self._game_over_menu_bounds = (
            menu_cx - button_w / 2,
            menu_cx + button_w / 2,
            menu_cy - button_h / 2,
            menu_cy + button_h / 2,
        )

        arcade.draw_rect_filled(arcade.rect.XYWH(resume_cx, resume_cy, button_w, button_h), (56, 104, 74, 235))
        arcade.draw_rect_outline(arcade.rect.XYWH(resume_cx, resume_cy, button_w, button_h), (220, 255, 220, 220), 2)
        arcade.draw_text(
            "Resume",
            resume_cx,
            resume_cy,
            arcade.color.WHITE,
            font_size=18,
            anchor_x="center",
            anchor_y="center",
            bold=True,
        )

        arcade.draw_rect_filled(arcade.rect.XYWH(menu_cx, menu_cy, button_w, button_h), (78, 78, 92, 235))
        arcade.draw_rect_outline(arcade.rect.XYWH(menu_cx, menu_cy, button_w, button_h), (220, 220, 240, 220), 2)
        arcade.draw_text(
            "Back to Menu",
            menu_cx,
            menu_cy,
            arcade.color.WHITE,
            font_size=18,
            anchor_x="center",
            anchor_y="center",
        )

    @staticmethod
    def _point_in_bounds(x: float, y: float, bounds: tuple[float, float, float, float] | None) -> bool:
        if bounds is None:
            return False
        left, right, bottom, top = bounds
        return left <= x <= right and bottom <= y <= top

    def _default_spawn_point(self) -> tuple[float, float]:
        """Berechnet den initialen Spawnpunkt dieser Welt."""
        spawn_x = SCREEN_WIDTH / 2
        ground_y = self.world.get_ground_top(int(spawn_x))
        spawn_y = ground_y + self.player.height / 2
        return float(spawn_x), float(spawn_y)

    def _respawn_player(self):
        """Setzt den Spieler auf den Welt-Spawnpunkt zurück."""
        spawn = self.world.get_spawn_point()
        if spawn is None:
            spawn = self._default_spawn_point()
            self.world.set_spawn_point(spawn[0], spawn[1])

        self.player.center_x = float(spawn[0])
        self.player.center_y = float(spawn[1])
        self.player.change_x = 0.0
        self.player.change_y = 0.0
        self.player.on_ground = False
        self.player.health = int(self.player.max_health)
        self.player.air_bubbles = int(self.player.max_air_bubbles)
        self.player.invincibility_timer = 1.0
        self.game_over = False
        self.left_pressed = False
        self.right_pressed = False
        self.jump_pressed = False
        self.camera.position = self._clamped_camera_position()

    def _drop_inventory_on_death(self):
        """Lässt den Spieler beim Tod alle Inventar-Items am Todesort fallen."""
        base_x = float(self.player.center_x)
        base_y = float(self.player.center_y)
        spread = TILE_SIZE * 0.28

        for slot in self.player.inventory.slots:
            if slot.item is None or slot.count <= 0:
                continue

            entry_id = int(slot.item)
            for _ in range(int(slot.count)):
                jitter_x = random.uniform(-spread, spread)
                jitter_y = random.uniform(-spread * 0.35, spread * 0.35)
                texture = self.player.inventory.get_texture(entry_id)
                if texture is None:
                    continue
                drop = DroppedItem(entry_id=entry_id, texture=texture, spawn_x=base_x + jitter_x, spawn_y=base_y + jitter_y)
                self.dropped_items.append(drop)
                self.dropped_item_sprite_list.append(drop.sprite)

            slot.item = None
            slot.count = 0

    def _handle_player_death(self):
        """Aktiviert Game Over und droppt das komplette Inventar einmalig."""
        if self.game_over:
            return
        self.player.health = 0
        self.player.change_x = 0.0
        self.player.change_y = 0.0
        self.player.finish_attack()
        if self.player.is_mining:
            self.player.cancel_mining()
        self._drop_inventory_on_death()
        self.game_over = True

    def _setup_start_menu_stub(self):
        """Initialisiert Startmenü-Daten für die Schüler-Challenge."""
        self.start_menu_seed_text = str(self.start_world_seed)

    def _draw_start_menu_stub(self):
        """Zeichnet ein einfaches Startmenü (optional aktivierbar)."""
        if not self.show_start_menu:
            return

        arcade.draw_rect_filled(
            arcade.rect.XYWH(self.width / 2, self.height / 2, self.width, self.height),
            (0, 0, 0, 210),
        )
        arcade.draw_text(
            "STARTMENÜ",
            self.width / 2,
            self.height / 2 + 90,
            arcade.color.WHITE,
            30,
            anchor_x="center",
            anchor_y="center",
            bold=True,
        )
        arcade.draw_text(
            f"Seed: {self.start_menu_seed_text or '-'}",
            self.width / 2,
            self.height / 2 + 30,
            arcade.color.WHITE,
            20,
            anchor_x="center",
            anchor_y="center",
        )
        arcade.draw_text(
            f"Fullscreen: {'AN' if self.start_fullscreen else 'AUS'}",
            self.width / 2,
            self.height / 2 - 6,
            arcade.color.WHITE,
            18,
            anchor_x="center",
            anchor_y="center",
        )
        arcade.draw_text(
            "Enter = Start, F = Fullscreen umschalten",
            self.width / 2,
            self.height / 2 - 42,
            arcade.color.LIGHT_GRAY,
            14,
            anchor_x="center",
            anchor_y="center",
        )

    def _apply_start_menu_options_stub(self):
        """Übernimmt Seed/Fullscreen aus dem Startmenü."""
        try:
            self.start_world_seed = int(self.start_menu_seed_text)
        except ValueError:
            self.start_world_seed = WORLD_SEED

        if self.window is not None:
            self.window.set_fullscreen(self.start_fullscreen)
        self.setup(seed_override=self.start_world_seed)

    def _handle_start_menu_key_stub(self, symbol: int):
        """Einfache Tastenlogik für das Startmenü."""
        if symbol == arcade.key.ENTER:
            self.show_start_menu = False
            self._apply_start_menu_options_stub()
            return True

        if symbol == arcade.key.F:
            self.start_fullscreen = not self.start_fullscreen
            return True

        if symbol == arcade.key.BACKSPACE:
            self.start_menu_seed_text = self.start_menu_seed_text[:-1]
            return True

        if 48 <= symbol <= 57:
            self.start_menu_seed_text += chr(symbol)
            return True

        return False

    def _mob_under_mouse(self, screen_x: float, screen_y: float):
        """Liefert den Mob unter der Maus oder None."""
        world_x, world_y = self._screen_to_world(screen_x, screen_y)
        for mob in reversed(self.mobs):
            left = mob.center_x - mob.collision_width / 2
            right = mob.center_x + mob.collision_width / 2
            bottom = mob.center_y - mob.collision_height / 2
            top = mob.center_y + mob.collision_height / 2
            if left <= world_x <= right and bottom <= world_y <= top:
                return mob
        return None

    def _resolve_player_attack(self):
        """Verarbeitet die aktive Nahkampf-Hitbox gegen alle Gegner."""
        if not self.player.is_attacking:
            return

        hit_left, hit_right, hit_bottom, hit_top = self.player.get_attack_hitbox()
        hit_direction = 1 if self.player.facing_right else -1

        for mob in self.mobs:
            if not getattr(mob, "alive", True):
                continue

            mob_id = id(mob)
            if mob_id in self.player.attack_hit_targets:
                continue

            mob_left = mob.center_x - mob.collision_width / 2
            mob_right = mob.center_x + mob.collision_width / 2
            mob_bottom = mob.center_y - mob.collision_height / 2
            mob_top = mob.center_y + mob.collision_height / 2

            if not aabb_overlap((hit_left, hit_right, hit_bottom, hit_top), (mob_left, mob_right, mob_bottom, mob_top)):
                continue

            self.player.attack_hit_targets.add(mob_id)
            mob.apply_knockback(hit_direction * 180.0, 120.0, stun_duration=0.35)
            killed = mob.take_damage(self.player.attack_damage)
            if killed:
                continue

    def _sync_torch_lights(self):
        """Synchronisiert Spieler-/Welt-Fackeln und gesampelte Lava-Lichter mit dem aktuellen Zustand."""
        if self._is_torch_equipped():
            light_pos = self.player.get_equipped_light_source_position()
            if light_pos is None:
                light_pos = (self.player.center_x, self.player.center_y)
            torch_daylight_scale = self._torch_daylight_multiplier(light_pos[0], light_pos[1])
            self.player_torch_light.position = light_pos
            self.player_torch_light.radius = 165.0 * torch_daylight_scale
            setattr(self.player_torch_light, "color", self.torch_light_color)
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
            radius = 165.0 * tile_scale
            if light is None:
                light = Light(light_x, light_y, radius=radius, color=self.torch_light_color, mode="soft")
                self.light_layer.add(light)
                self.placed_torch_lights[tile_pos] = light
            else:
                light.position = (light_x, light_y)
                light.radius = radius
                setattr(light, "color", self.torch_light_color)

        lava_samples = self.lighting.collect_visible_lava_light_samples()
        current_lava_tiles = {(sample.tile_x, sample.tile_y) for sample in lava_samples}
        existing_lava_tiles = set(self.sampled_lava_lights.keys())

        for tile_pos in existing_lava_tiles - current_lava_tiles:
            light = self.sampled_lava_lights.pop(tile_pos)
            self.light_layer.remove(light)

        for sample in lava_samples:
            tile_pos = (sample.tile_x, sample.tile_y)
            light = self.sampled_lava_lights.get(tile_pos)
            warm_strength = max(0.0, min(1.0, sample.strength))
            color = (
                int(220 + 35 * warm_strength),
                int(86 + 64 * warm_strength),
                int(44 + 22 * warm_strength),
            )

            if light is None:
                light = Light(sample.world_x, sample.world_y, radius=sample.radius, color=color, mode="soft")
                self.light_layer.add(light)
                self.sampled_lava_lights[tile_pos] = light
            else:
                light.position = (sample.world_x, sample.world_y)
                light.radius = sample.radius
                setattr(light, "color", color)

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

    def _draw_moon_no_ambient(self):
        """Wrapper to draw moon texture in a non-ambient pass."""
        self.lighting.draw_moon_no_ambient()

    def _draw_stars_no_ambient(self):
        """Wrapper to draw stars in a non-ambient pass."""
        self.lighting.draw_stars_no_ambient()

    def _spawn_dropped_item(self, entry_id: int, tile_x: int, tile_y: int):
        """Erzeugt ein physisches Item an der Blockposition."""
        texture = self.player.inventory.get_texture(entry_id)
        if texture is None:
            return

        spawn_x, spawn_y = self.world.to_world_position(tile_x, tile_y)
        drop = DroppedItem(entry_id=entry_id, texture=texture, spawn_x=spawn_x, spawn_y=spawn_y)
        self.dropped_items.append(drop)
        self.dropped_item_sprite_list.append(drop.sprite)

    def _throw_selected_hotbar_item(self) -> bool:
        """Wirft ein Item aus dem aktiven Hotbar-Slot vor den Spieler."""
        slot_index = self.player.inventory.HOTBAR_START + self.player.selected_hotbar_slot
        slot = self.player.inventory.get_slot(slot_index)
        if slot is None or slot.item is None or slot.count <= 0:
            return False

        entry_id = int(slot.item)
        texture = self.player.inventory.get_texture(entry_id)
        if texture is None:
            return False

        direction = 1.0 if self.player.facing_right else -1.0
        spawn_x = self.player.center_x + direction * self.item_throw_spawn_distance
        spawn_y = self.player.center_y + self.player.height * 0.1

        drop = DroppedItem(
            entry_id=entry_id,
            texture=texture,
            spawn_x=spawn_x,
            spawn_y=spawn_y,
            initial_vx=direction * self.item_throw_speed,
            initial_vy=self.item_throw_upward_speed,
            pickup_delay_seconds=self.item_throw_pickup_delay,
        )
        self.dropped_items.append(drop)
        self.dropped_item_sprite_list.append(drop.sprite)

        slot.count -= 1
        if slot.count <= 0:
            slot.item = None
            slot.count = 0

        self.hotbar.trigger_render()
        self.health_ui.trigger_render()
        self.bubble_ui.trigger_render()
        if self.inventory_ui.visible:
            self.inventory_ui.trigger_render()
        return True

    def _update_dropped_items(self, delta_time: float, allow_pickup: bool = True):
        """Aktualisiert Drop-Physik und sammelt optional erreichbare Items auf."""
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

            if getattr(drop, "expired", False):
                self.dropped_item_sprite_list.remove(drop.sprite)
                continue

            if allow_pickup and wants_pickup:
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

    def _active_drop_chunk_xs(self) -> set[int]:
        """Ermittelt Chunks, die gedroppte Items enthalten, damit sie geladen bleiben."""
        chunk_xs: set[int] = set()
        for drop in self.dropped_items:
            tile_x = int(math.floor(drop.sprite.center_x / TILE_SIZE))
            chunk_x, _ = world_to_chunk_and_local(tile_x)
            chunk_xs.add(chunk_x)
        return chunk_xs

    def _rebuild_world_sprites(self):
        """Erzeugt den Block- und Wasser-Sprite-Cache für den aktuellen Sichtbereich neu."""
        min_tile_y, max_tile_y = self._get_target_render_tile_range()
        self.chunk_sprite_lists = {}
        self.chunk_sprite_maps = {}
        self.water_sprite_list = arcade.SpriteList()
        self.water_sprite_maps = {}
        self.lava_sprite_list = arcade.SpriteList()
        self.lava_sprite_maps = {}
        for chunk_x in sorted(self.world.chunks):
            chunk = self.world.chunks[chunk_x]
            sprite_list, sprite_map = build_chunk_sprite_list(chunk_x, chunk, min_tile_y, max_tile_y)
            self.chunk_sprite_lists[chunk_x] = sprite_list
            self.chunk_sprite_maps[chunk_x] = sprite_map

            water_sprites, water_map = build_chunk_water_sprite_list(
                chunk_x,
                chunk,
                min_tile_y,
                max_tile_y,
                include_map=True,
            )
            for sprite in water_sprites:
                self.water_sprite_list.append(sprite)
            self.water_sprite_maps[chunk_x] = water_map

            lava_sprites, lava_map = build_chunk_lava_sprite_list(
                chunk_x,
                chunk,
                min_tile_y,
                max_tile_y,
                include_map=True,
            )
            for sprite in lava_sprites:
                self.lava_sprite_list.append(sprite)
            self.lava_sprite_maps[chunk_x] = lava_map
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
            removed_water = self.water_sprite_maps.pop(chunk_x, None)
            if removed_water is not None:
                for sprite in removed_water.values():
                    self.water_sprite_list.remove(sprite)
            removed_lava = self.lava_sprite_maps.pop(chunk_x, None)
            if removed_lava is not None:
                for sprite in removed_lava.values():
                    self.lava_sprite_list.remove(sprite)

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

            old_water = self.water_sprite_maps.pop(chunk_x, None)
            if old_water is not None:
                for sprite in old_water.values():
                    self.water_sprite_list.remove(sprite)

            water_sprites, water_map = build_chunk_water_sprite_list(
                chunk_x,
                chunk,
                min_tile_y,
                max_tile_y,
                include_map=True,
            )
            for sprite in water_sprites:
                self.water_sprite_list.append(sprite)
            self.water_sprite_maps[chunk_x] = water_map

            old_lava = self.lava_sprite_maps.pop(chunk_x, None)
            if old_lava is not None:
                for sprite in old_lava.values():
                    self.lava_sprite_list.remove(sprite)

            lava_sprites, lava_map = build_chunk_lava_sprite_list(
                chunk_x,
                chunk,
                min_tile_y,
                max_tile_y,
                include_map=True,
            )
            for sprite in lava_sprites:
                self.lava_sprite_list.append(sprite)
            self.lava_sprite_maps[chunk_x] = lava_map

    def _apply_world_water_diffs(self, changes: list[tuple[int, int, float, float]]):
        """Aktualisiert Wasser-Sprites gezielt pro geänderter Zelle statt Voll-Rebuild."""
        if not changes:
            return

        if self.render_tile_range is None:
            min_tile_y, max_tile_y = self._get_target_render_tile_range()
            self.render_tile_range = (min_tile_y, max_tile_y)
        else:
            min_tile_y, max_tile_y = self.render_tile_range

        for tile_x, tile_y, _old_value, new_value in changes:
            chunk_x, local_x = world_to_chunk_and_local(tile_x)
            chunk = self.world.chunks.get(chunk_x)
            if chunk is None:
                continue

            chunk_water_map = self.water_sprite_maps.setdefault(chunk_x, {})
            key = (local_x, tile_y)
            existing_sprite = chunk_water_map.get(key)

            in_visible_band = min_tile_y <= tile_y <= max_tile_y
            block_id = chunk.get_block(local_x, tile_y)
            block_open_for_water = block_id == AIR or not is_block_solid(block_id)
            normalized = max(0.0, min(1.0, float(new_value)))
            target_height = get_water_render_height(normalized)
            if target_height <= 0.0 and normalized > 0.0:
                above = self.world.get_water(tile_x, tile_y + 1)
                # Nur von oben haengende Restmengen als duennen Slice zeichnen.
                if above >= WATER_RENDER_THRESHOLD:
                    target_height = TILE_SIZE / WATER_VISUAL_STEPS
            should_render = in_visible_band and block_open_for_water and target_height > 0.0

            if 0.0 < normalized < WATER_RENDER_THRESHOLD:
                below_block_id = self.world.get_block(tile_x, tile_y - 1, generate_if_missing=False)
                below_open_for_water = below_block_id == AIR or not is_block_solid(below_block_id)
                if below_open_for_water:
                    debug_key = (tile_x, tile_y)
                    if debug_key not in self._debug_logged_tiny_edge_cells:
                        print(
                            "[water-edge-debug] cell="
                            f"({tile_x},{tile_y}) water={normalized:.12f} "
                            f"render_threshold={WATER_RENDER_THRESHOLD:.3f} "
                            f"below_block={below_block_id}"
                        )
                        self._debug_logged_tiny_edge_cells.add(debug_key)

            if not should_render:
                if existing_sprite is not None:
                    self.water_sprite_list.remove(existing_sprite)
                    chunk_water_map.pop(key, None)
                continue

            target_center_x = (tile_x + 0.5) * TILE_SIZE
            target_center_y = (tile_y + (target_height / TILE_SIZE) / 2.0) * TILE_SIZE
            target_alpha = 128

            if existing_sprite is not None:
                existing_sprite.width = TILE_SIZE
                existing_sprite.height = target_height
                existing_sprite.center_x = target_center_x
                existing_sprite.center_y = target_center_y
                existing_sprite.alpha = target_alpha
                existing_sprite.color = (120, 170, 255)
                continue

            sprite = arcade.Sprite(WATER_TEXTURE)
            sprite.center_x = target_center_x
            sprite.center_y = target_center_y
            sprite.width = TILE_SIZE
            sprite.height = target_height
            sprite.alpha = target_alpha
            sprite.color = (120, 170, 255)

            self.water_sprite_list.append(sprite)
            chunk_water_map[key] = sprite

    def _apply_world_lava_diffs(self, changes: list[tuple[int, int, float, float]]):
        """Aktualisiert Lava-Sprites gezielt pro geänderter Zelle statt Voll-Rebuild."""
        if not changes:
            return

        if self.render_tile_range is None:
            min_tile_y, max_tile_y = self._get_target_render_tile_range()
            self.render_tile_range = (min_tile_y, max_tile_y)
        else:
            min_tile_y, max_tile_y = self.render_tile_range

        for tile_x, tile_y, _old_value, new_value in changes:
            chunk_x, local_x = world_to_chunk_and_local(tile_x)
            chunk = self.world.chunks.get(chunk_x)
            if chunk is None:
                continue

            chunk_lava_map = self.lava_sprite_maps.setdefault(chunk_x, {})
            key = (local_x, tile_y)
            existing_sprite = chunk_lava_map.get(key)

            in_visible_band = min_tile_y <= tile_y <= max_tile_y
            block_id = chunk.get_block(local_x, tile_y)
            block_open_for_lava = block_id == AIR or not is_block_solid(block_id)
            normalized = max(0.0, min(1.0, float(new_value)))
            target_height = get_lava_render_height(normalized)
            should_render = in_visible_band and block_open_for_lava and target_height > 0.0

            if not should_render:
                if existing_sprite is not None:
                    self.lava_sprite_list.remove(existing_sprite)
                    chunk_lava_map.pop(key, None)
                continue

            target_center_x = (tile_x + 0.5) * TILE_SIZE
            target_center_y = (tile_y + (target_height / TILE_SIZE) / 2.0) * TILE_SIZE
            target_alpha = 200

            if existing_sprite is not None:
                existing_sprite.width = TILE_SIZE
                existing_sprite.height = target_height
                existing_sprite.center_x = target_center_x
                existing_sprite.center_y = target_center_y
                existing_sprite.alpha = target_alpha
                existing_sprite.color = (255, 255, 255)
                continue

            sprite = arcade.Sprite(LAVA_TEXTURE)
            sprite.center_x = target_center_x
            sprite.center_y = target_center_y
            sprite.width = TILE_SIZE
            sprite.height = target_height
            sprite.alpha = target_alpha
            sprite.color = (255, 255, 255)

            self.lava_sprite_list.append(sprite)
            chunk_lava_map[key] = sprite

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

    def setup(self, seed_override: int | None = None):
        """Initialisiert den Spielzustand."""
        if self.light_layer is None or self.lighting is None:
            return

        self.game_over = False
        self.frame_count = 0
        self.world = World(seed=self.start_world_seed if seed_override is None else seed_override)
        self.player = Player(world=self.world)
        spawn_x, spawn_y = self._default_spawn_point()
        self.world.set_spawn_point(spawn_x, spawn_y)
        self.player.center_x = spawn_x
        self.player.center_y = spawn_y
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
        self.mob_sprite_list = arcade.SpriteList()
        self.mobs = []
        self.mob_spawn_timer = 0.0
        self.hotbar = Hotbar(self.player)
        self.health_ui = HealthUI(self.player, self.hotbar)
        self.bubble_ui = BubbleUI(self.player, self.hotbar, self.health_ui)
        self.inventory_ui = InventoryUI(self.player, SCREEN_WIDTH, SCREEN_HEIGHT)
        self.ui_manager.clear()
        self.inventory_anchor = arcade.gui.UIAnchorLayout(size_hint=(1.0, 1.0))
        self.ui_manager.add(self.bubble_ui)
        self.ui_manager.add(self.hotbar)
        self.ui_manager.add(self.health_ui)
        self.ui_manager.add(self.inventory_anchor)
        self.inventory_anchor.add(self.inventory_ui, anchor_x="center", anchor_y="center")
        self.jump_pressed = False
        self.physics = AABBPhysics(self.world)
        for light in list(self.light_layer):
            self.light_layer.remove(light)
        self.player_torch_light = Light(0.0, 0.0, radius=0.0, color=self.torch_light_color, mode="soft")
        self.light_layer.add(self.player_torch_light)
        self.placed_torch_lights = {}
        self.sampled_lava_lights = {}
        self.chunk_sprite_lists = {}
        self.chunk_sprite_maps = {}
        self.water_sprite_maps = {}
        self.lava_sprite_maps = {}
        self._debug_logged_tiny_edge_cells = set()
        self.render_tile_range = None

        if self._pending_save_data is not None:
            self._restore_from_save_data(self._pending_save_data)
            self._pending_save_data = None
            return

        self.camera.position = self._clamped_camera_position()
        self.world.update_loaded_chunks(self.player.center_x)
        self._rebuild_world_sprites()
        self.light_layer.resize(int(self.width), int(self.height))
        self._sync_torch_lights()

    @staticmethod
    def _decode_saved_chunk_blocks(raw_data) -> dict[int, list[list[int]]]:
        decoded: dict[int, list[list[int]]] = {}
        if not isinstance(raw_data, dict):
            return decoded
        for chunk_key, blocks in raw_data.items():
            try:
                chunk_x = int(chunk_key)
            except (TypeError, ValueError):
                continue
            if not isinstance(blocks, list):
                continue
            decoded[chunk_x] = [list(row) for row in blocks if isinstance(row, list)]
        return decoded

    @staticmethod
    def _decode_saved_chunk_liquid(raw_data) -> dict[int, dict[tuple[int, int], float]]:
        decoded: dict[int, dict[tuple[int, int], float]] = {}
        if not isinstance(raw_data, dict):
            return decoded

        for chunk_key, cells in raw_data.items():
            try:
                chunk_x = int(chunk_key)
            except (TypeError, ValueError):
                continue

            if not isinstance(cells, list):
                continue

            chunk_liquid: dict[tuple[int, int], float] = {}
            for cell in cells:
                if not isinstance(cell, (list, tuple)) or len(cell) != 3:
                    continue
                local_x = int(cell[0])
                y = int(cell[1])
                amount = float(cell[2])
                if amount <= 0.0:
                    continue
                chunk_liquid[(local_x, y)] = max(0.0, min(1.0, amount))

            decoded[chunk_x] = chunk_liquid
        return decoded

    def _restore_inventory_slots_from_save(self, save_slots) -> None:
        if not isinstance(save_slots, list):
            return

        for slot in self.player.inventory.slots:
            slot.item = None
            slot.count = 0

        max_slot_count = min(len(save_slots), len(self.player.inventory.slots))
        for index in range(max_slot_count):
            entry = save_slots[index]
            if not isinstance(entry, dict):
                continue
            item = entry.get("item")
            count = int(entry.get("count", 0))
            if item is None or count <= 0:
                continue
            self.player.inventory.slots[index].item = int(item)
            self.player.inventory.slots[index].count = count

    def _restore_from_save_data(self, save_data: dict) -> None:
        world_data = save_data.get("world", {}) if isinstance(save_data, dict) else {}
        player_data = save_data.get("player", {}) if isinstance(save_data, dict) else {}
        inventory_data = save_data.get("inventory", {}) if isinstance(save_data, dict) else {}
        state_data = save_data.get("state", {}) if isinstance(save_data, dict) else {}
        meta_data = save_data.get("meta", {}) if isinstance(save_data, dict) else {}

        save_seed = world_data.get("seed")
        if save_seed is not None:
            self.start_world_seed = int(save_seed)
            self.world.seed = int(save_seed)

        loaded_name = meta_data.get("world_name")
        if isinstance(loaded_name, str) and loaded_name.strip():
            self.world_name = loaded_name.strip()

        self.world.chunks = {}
        self.world.saved_chunk_blocks = self._decode_saved_chunk_blocks(world_data.get("changed_blocks"))
        self.world.saved_chunk_water = self._decode_saved_chunk_liquid(world_data.get("changed_water"))
        self.world.saved_chunk_lava = self._decode_saved_chunk_liquid(world_data.get("changed_lava"))
        self.world.pending_generated_blocks = {}

        placed_items: dict[tuple[int, int], int] = {}
        for entry in world_data.get("items", []):
            if not isinstance(entry, (list, tuple)) or len(entry) != 3:
                continue
            world_x = int(entry[0])
            tile_y = int(entry[1])
            item_id = int(entry[2])
            placed_items[(world_x, tile_y)] = item_id
        self.world.placed_items = placed_items

        spawn_data = world_data.get("spawn_point", {}) if isinstance(world_data, dict) else {}
        spawn_x = spawn_data.get("x") if isinstance(spawn_data, dict) else None
        spawn_y = spawn_data.get("y") if isinstance(spawn_data, dict) else None
        if isinstance(spawn_x, (int, float)) and isinstance(spawn_y, (int, float)):
            self.world.set_spawn_point(float(spawn_x), float(spawn_y))
        else:
            default_spawn_x, default_spawn_y = self._default_spawn_point()
            self.world.set_spawn_point(default_spawn_x, default_spawn_y)

        self.player.center_x = float(player_data.get("position", {}).get("x", self.player.center_x))
        self.player.center_y = float(player_data.get("position", {}).get("y", self.player.center_y))
        self.player.change_x = float(player_data.get("velocity", {}).get("x", 0.0))
        self.player.change_y = float(player_data.get("velocity", {}).get("y", 0.0))
        self.player.max_health = int(player_data.get("max_health", self.player.max_health))
        self.player.health = int(player_data.get("health", self.player.health))
        self.player.max_air_bubbles = int(player_data.get("max_air_bubbles", self.player.max_air_bubbles))
        self.player.air_bubbles = int(player_data.get("air_bubbles", self.player.air_bubbles))
        self.player.selected_hotbar_slot = max(
            0,
            min(
                self.player.inventory.HOTBAR_SIZE - 1,
                int(player_data.get("selected_hotbar_slot", self.player.selected_hotbar_slot)),
            ),
        )
        facing_right = bool(player_data.get("facing_right", True))
        self.player.facing_right = facing_right
        self.player.scale_x = 1.0 if facing_right else -1.0

        self._restore_inventory_slots_from_save(inventory_data.get("slots", []))

        self.time_of_day = float(state_data.get("time_of_day", self.time_of_day)) % 1.0

        if self._restore_runtime_state and isinstance(state_data, dict):
            inventory_ui_open = bool(state_data.get("inventory_ui_open", False))
            self.inventory_ui.visible = inventory_ui_open

        self.camera.position = self._clamped_camera_position()
        self.world.update_loaded_chunks(self.player.center_x)
        self._rebuild_world_sprites()
        self.light_layer.resize(int(self.width), int(self.height))
        self._sync_torch_lights()

    def spawn_mob(self, mob_class, x: float, y: float, **mob_kwargs):
        """Spawns any mob class at the requested world position."""
        if len(self.mobs) >= self.max_active_mobs:
            print("[mob-spawn] skipped: max mob count reached")
            return None

        return spawn_mob_at(
            self.world,
            mob_class,
            self.mobs,
            self.mob_sprite_list,
            x=x,
            y=y,
            **mob_kwargs,
        )

    def on_update(self, delta_time: float):
        """Wird regelmäßig pro Frame aufgerufen."""
        if self.game_over:
            physics_delta = min(delta_time, 1 / 30)
            self.world.update(
                physics_delta,
                center_x=self.player.center_x,
                center_y=self.player.center_y,
                player=None,
                update_chunks=False,
            )

            water_changes = self.world.consume_changed_water()
            if water_changes:
                self._apply_world_water_diffs(water_changes)

            lava_changes = self.world.consume_changed_lava()
            if lava_changes:
                self._apply_world_lava_diffs(lava_changes)

            self._update_dropped_items(physics_delta, allow_pickup=False)
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

        physics_delta = min(delta_time, 1 / 30)

        self.player.refresh_water_state()
        if self.left_pressed and not self.right_pressed:
            self.player.move_left()
        elif self.right_pressed and not self.left_pressed:
            self.player.move_right()
        elif self.player.on_ground:
            self.player.stop_horizontal()

        self.player.apply_swim_input(self.jump_pressed, physics_delta)

        was_on_ground = self.player.on_ground
        self.physics.update(self.player, physics_delta)
        if was_on_ground and not self.player.on_ground:
            self.player.begin_fall_tracking()
        elif not was_on_ground and self.player.on_ground:
            self.player.apply_fall_damage()

        self.player.refresh_water_state()
        self.player.update_water_breathing(physics_delta)
        self.player.update(physics_delta)
        self.world.update(
            physics_delta,
            center_x=self.player.center_x,
            center_y=self.player.center_y,
            player=self.player,
            update_chunks=False,
        )

        for drop_id, tile_x, tile_y in self.player.consume_pending_item_drops():
            self._spawn_dropped_item(drop_id, tile_x, tile_y)
        self._update_dropped_items(physics_delta)

        if self.left_mouse_held and self.left_mouse_mining_chain and not self.inventory_ui.visible:
            target = self._get_block_from_mouse(self.mouse_screen_x, self.mouse_screen_y)
            if target is None:
                if self.player.is_mining:
                    self.player.cancel_mining()
            else:
                tile_x, tile_y, _ = target
                target_pos = (tile_x, tile_y)
                if self.player.is_mining:
                    if self.player.mining_target != target_pos:
                        self.player.cancel_mining()
                        self.player.start_mining(target_pos)
                else:
                    self.player.start_mining(target_pos)

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
        self.lighting.notify_world_block_changes(block_changes)
        if block_changes and not did_full_rebuild:
            self._apply_world_block_diffs(block_changes)

        water_changes = self.world.consume_changed_water()
        if water_changes and not did_full_rebuild:
            self._apply_world_water_diffs(water_changes)

        lava_changes = self.world.consume_changed_lava()
        if lava_changes and not did_full_rebuild:
            self._apply_world_lava_diffs(lava_changes)

        if self.player.world_dirty:
            self.player.world_dirty = False
            self.player.dirty_chunk_xs.clear()

        loaded_chunks, unloaded_chunks = self.world.update_loaded_chunks(
            self.player.center_x,
            max_loads=self.max_chunk_loads_per_frame,
            max_unloads=self.max_chunk_unloads_per_frame,
            keep_loaded_chunk_xs=self._active_drop_chunk_xs(),
        )

        # Reconcile cache keys with actual loaded chunk keys to avoid missing visuals.
        loaded_chunk_set = set(loaded_chunks)
        unloaded_chunk_set = set(unloaded_chunks)
        loaded_chunk_set.update(set(self.world.chunks.keys()) - set(self.chunk_sprite_lists.keys()))
        unloaded_chunk_set.update(set(self.chunk_sprite_lists.keys()) - set(self.world.chunks.keys()))

        if loaded_chunk_set or unloaded_chunk_set:
            self._sync_chunk_sprite_cache(sorted(loaded_chunk_set), sorted(unloaded_chunk_set))

        self._sync_torch_lights()
        self._update_mobs(delta_time)

        if self.player.health <= 0:
            self._handle_player_death()

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

    def _can_spawn_mob_at(self, world_x: float, world_y: float, ignore_player_distance: bool = False) -> bool:
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

    def _spawn_mob_if_needed(self):
        """Spawns roaming mobs depending on day/night conditions."""
        if len(self.mobs) >= self.max_active_mobs:
            return
        if self.mob_spawn_timer > 0.0:
            return

        is_night = self._day_factor() < 0.35
        spawn_pool: list[type] = [Chicken]
        if is_night:
            spawn_pool = [Slime, Zombie, Chicken]

        for _ in range(24):
            mob_class = random.choice(spawn_pool)
            angle = random.uniform(0.0, 2.0 * math.pi)
            distance = random.uniform(700.0, 1800.0)
            spawn_x = self.player.center_x + math.cos(angle) * distance
            spawn_tile_x = int(spawn_x // TILE_SIZE)
            ground_y = self.world.get_ground_top(spawn_tile_x)
            spawn_y = ground_y + 14.0

            if not self._can_spawn_mob_at(spawn_x, spawn_y):
                continue

            spawned = self.spawn_mob(mob_class, spawn_x, spawn_y)
            if spawned is not None:
                self.mob_spawn_timer = 3.0 if mob_class is Slime else 5.0
                return

    def _update_mobs(self, delta_time: float):
        """Aktualisiert alle Mobs und entfernt tote Mobs erst nach dem Verfallszeitpunkt."""
        alive_mobs: list[Mob] = []
        for mob in self.mobs:
            mob.update(delta_time, self.player)

            if not getattr(mob, "alive", True):
                if getattr(mob, "vanish_after_death_timer", 0.0) <= 0.0:
                    self.mob_sprite_list.remove(mob)
                    continue
                alive_mobs.append(mob)
                continue

            if mob.center_y < -64:
                self.mob_sprite_list.remove(mob)
                continue
            alive_mobs.append(mob)

        self.mobs = alive_mobs
        self.mob_spawn_timer = max(0.0, self.mob_spawn_timer - delta_time)
        self._spawn_mob_if_needed()

    def on_draw(self):
        """Zeichnet die Szene und die Minecraft-artige Hotbar."""
        self.clear((0, 0, 0, 255))

        with self.light_layer:
            self._draw_sky_shader()

            self.ui_camera.use()
            self._draw_stars_no_ambient()

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
            self.mob_sprite_list.draw()
            self.player.draw_held_item(layer="back")
            self.player_sprite_list.draw()
            self.player.draw_held_item(layer="front")
            self.mining_sprite_list.draw()
            self.water_sprite_list.draw()
            self.lava_sprite_list.draw()
            self._draw_underground_darkness_overlay()

        self.light_layer.draw(ambient_color=self._ambient_color())

        self.ui_camera.use()
        self._draw_moon_no_ambient()

        self.ui_camera.use()
        self.hotbar.trigger_render()
        self.health_ui.trigger_render()
        self.bubble_ui.trigger_render()
        if self.inventory_ui.visible:
            # Dynamische Slot-Inhalte koennen sich pro Frame aendern.
            self.inventory_ui.trigger_render()
        self.ui_manager.draw()
        self.fps_text.y = self.height - 16
        self.fps_text.draw()

        if self.game_over:
            self._draw_game_over_overlay()

    def _place_water_at_mouse_cursor(self):
        """Platziert ein volles Wasser-Volume im nächsten freien Luft-Block unter der Maus."""
        if self.mouse_screen_x is None or self.mouse_screen_y is None:
            return None

        world_x, world_y = self._screen_to_world(self.mouse_screen_x, self.mouse_screen_y)
        tile_x, tile_y = self.world.to_block_position(world_x, world_y)

        target_x = tile_x
        target_y = tile_y
        block_at_cursor = self.world.get_block(tile_x, tile_y, generate_if_missing=False)
        if block_at_cursor != AIR and is_block_solid(block_at_cursor):
            target_y = None
            for offset in range(1, 8):
                candidate_y = tile_y + offset
                candidate_block = self.world.get_block(tile_x, candidate_y, generate_if_missing=False)
                if candidate_block == AIR or not is_block_solid(candidate_block):
                    target_y = candidate_y
                    break
            if target_y is None:
                return None

        self.world.set_water(target_x, target_y, 1.0)
        self._rebuild_world_sprites()
        return target_x, target_y

    def on_key_press(self, symbol: int, modifiers: int):
        """Reagiert auf Tastatureingaben."""
        if self.game_over:
            if symbol == arcade.key.ENTER:
                self._respawn_player()
            elif symbol == arcade.key.ESCAPE and self.window is not None:
                from start_menu_view import StartMenuView

                self.window.show_view(StartMenuView())
            return

        if symbol == arcade.key.ESCAPE and self.window is not None:
            self.window.show_view(GameMenuView(self))
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

        if cmd_down and symbol == arcade.key.U:
            self.lighting.use_cpu_underground_overlay_debug = not self.lighting.use_cpu_underground_overlay_debug
            mode = "CPU" if self.lighting.use_cpu_underground_overlay_debug else "GPU"
            print(f"[lighting] underground overlay mode: {mode}")
            return

        if symbol == arcade.key.P:
            spawn_mob_next_to_player(
                self.world,
                self.player,
                DEBUG_SPAWN_MOB_CLASS,
                self.mobs,
                self.mob_sprite_list,
            )
            return

        if 49 <= symbol <= 57:
            slot_index = symbol - 49
            self.player.select_hotbar_slot(slot_index)
            self.hotbar.trigger_render()
            self.health_ui.trigger_render()
            self.bubble_ui.trigger_render()
            if self.inventory_ui.visible:
                self.inventory_ui.trigger_render()
            return

        if symbol in (arcade.key.A, arcade.key.LEFT):
            self.left_pressed = True
            self.right_pressed = False
            self.player.move_left()
        elif symbol in (arcade.key.D, arcade.key.RIGHT):
            self.right_pressed = True
            self.left_pressed = False
            self.player.move_right()
        elif symbol == arcade.key.Q:
            if self._throw_selected_hotbar_item():
                return
        elif symbol == arcade.key.SPACE or symbol == arcade.key.UP or symbol == arcade.key.W:
            self.jump_pressed = True
            if self.player.in_water or self.player.feet_in_water:
                return
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
        elif symbol in (arcade.key.SPACE, arcade.key.UP, arcade.key.W):
            self.jump_pressed = False

        if not self.left_pressed and not self.right_pressed:
            self.player.stop_horizontal()
        elif self.left_pressed and not self.right_pressed:
            self.player.move_left()
        elif self.right_pressed and not self.left_pressed:
            self.player.move_right()

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        """Verarbeitet Links- und Rechtsklicks für Abbauen, Platzieren und Inventar-Interaktion."""
        if self.game_over:
            if button == arcade.MOUSE_BUTTON_LEFT:
                if self._point_in_bounds(x, y, self._game_over_resume_bounds):
                    self._respawn_player()
                    return
                if self._point_in_bounds(x, y, self._game_over_menu_bounds):
                    from start_menu_view import StartMenuView

                    if self.window is not None:
                        self.window.show_view(StartMenuView())
                    return
            return

        self.mouse_screen_x = x
        self.mouse_screen_y = y

        if self.inventory_ui.visible:
            return

        if button == arcade.MOUSE_BUTTON_LEFT:
            self.left_mouse_held = True
            self.left_mouse_mining_chain = False
            mob = self._mob_under_mouse(x, y)
            if mob is not None:
                self.player.start_attack()
                return

            placed_item = self._get_placed_item_from_mouse(x, y)
            if placed_item is not None:
                tile_x, tile_y, item_id = placed_item
                removed_item = self.world.remove_placed_item(tile_x, tile_y)
                if removed_item is not None:
                    self._spawn_dropped_item(removed_item, tile_x, tile_y)

                return

            target = self._get_block_from_mouse(x, y)
            if target is None:
                self.player.start_attack()
                return

            tile_x, tile_y, _ = target
            self.player.start_mining((tile_x, tile_y))
            self.left_mouse_mining_chain = True

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
            self.left_mouse_held = False
            self.left_mouse_mining_chain = False
            if self.player.is_mining:
                self.player.cancel_mining()

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float):
        """Merkt die letzte Mausposition für Hold-to-Mine."""
        self.mouse_screen_x = x
        self.mouse_screen_y = y

    def on_mouse_drag(self, x: float, y: float, dx: float, dy: float, buttons: int, modifiers: int):
        """Merkt die letzte Mausposition auch beim Ziehen."""
        self.mouse_screen_x = x
        self.mouse_screen_y = y

    def on_resize(self, width: int, height: int):
        """Passt abhängige Systeme bei Fenstergrößenänderung an."""
        super().on_resize(width, height)
        self.camera.match_window()
        self.ui_camera.match_window()
        if self.light_layer is not None:
            self.light_layer.resize(int(width), int(height))
        self.inventory_ui.update_screen_size(width, height)
        self.hotbar.trigger_full_render()
        self.health_ui.trigger_full_render()
        self.bubble_ui.trigger_full_render()
        self.inventory_ui.trigger_full_render()


def main(load_save_path: str | None = None, dev_autosave_name: str | None = None):
    """Startet die Spielschleife."""
    from start_menu_view import StartMenuView

    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, WINDOW_TITLE)

    def _serialize_view_type(view: arcade.View) -> str:
        view_type = view.__class__
        return f"{view_type.__module__}:{view_type.__name__}"

    def _resolve_game_context(current: arcade.View | None) -> tuple[GameView | None, list[str]]:
        if current is None:
            return None, []

        overlays_top_to_bottom: list[str] = []
        seen: set[int] = set()
        cursor: arcade.View | None = current
        while cursor is not None and id(cursor) not in seen:
            seen.add(id(cursor))
            if isinstance(cursor, GameView):
                overlays_bottom_to_top = list(reversed(overlays_top_to_bottom))
                return cursor, overlays_bottom_to_top

            parent = getattr(cursor, "game_view", None)
            if not isinstance(parent, arcade.View):
                return None, []

            overlays_top_to_bottom.append(_serialize_view_type(cursor))
            cursor = parent

        return None, []

    def _restore_overlay_chain(game_view: GameView, overlay_chain: list[str]) -> None:
        if window.current_view is not game_view:
            return
        owner_view: arcade.View = game_view
        for raw_key in overlay_chain:
            if not isinstance(raw_key, str):
                continue
            overlay_key = raw_key.strip()
            if not overlay_key:
                continue

            overlay_view = game_view._build_restore_overlay_view(overlay_key, owner_view=owner_view)
            if overlay_view is None:
                continue

            window.show_view(overlay_view)
            owner_view = overlay_view

    def _active_game_view() -> GameView | None:
        game_view, _overlay_chain = _resolve_game_context(window.current_view)
        return game_view

    def _save_dev_state(reason: str) -> None:
        if not dev_autosave_name:
            return
        current_view = window.current_view
        view = _active_game_view()
        if view is None:
            return

        _resolved_view, overlay_chain = _resolve_game_context(current_view)
        runtime_state: dict[str, object] = {
            "inventory_ui_open": bool(view.inventory_ui.visible),
            "active_overlay_views": overlay_chain,
        }
        if overlay_chain:
            runtime_state["active_overlay_view"] = overlay_chain[-1]
            if overlay_chain[-1] == "game_menu_view:GameMenuView":
                # Rueckwaertskompatibel fuer fruehere Restore-Logik.
                runtime_state["active_view"] = "game_menu"
        try:
            save_path = save_game(view, save_name=dev_autosave_name, runtime_state=runtime_state)
            print(f"[dev-save] wrote {save_path} ({reason})")
        except Exception as exc:
            print(f"[dev-save] failed ({reason}): {exc}")

    if dev_autosave_name:
        atexit.register(lambda: _save_dev_state("atexit"))

        def _handle_shutdown(sig, _frame):
            _save_dev_state(f"signal {sig}")
            raise SystemExit(0)

        signal.signal(signal.SIGTERM, _handle_shutdown)
        signal.signal(signal.SIGINT, _handle_shutdown)

    if START_FULLSCREEN:
        window.set_fullscreen(True)

    did_load = False
    if load_save_path:
        try:
            is_dev_restore = bool(dev_autosave_name)
            save_payload = load_save(Path(load_save_path))
            world_data = save_payload.get("world", {}) if isinstance(save_payload, dict) else {}
            meta_data = save_payload.get("meta", {}) if isinstance(save_payload, dict) else {}
            state_data = save_payload.get("state", {}) if isinstance(save_payload, dict) else {}
            raw_seed = world_data.get("seed", WORLD_SEED) if isinstance(world_data, dict) else WORLD_SEED
            try:
                seed = int(raw_seed)
            except (TypeError, ValueError):
                seed = int(WORLD_SEED)
            world_name = str(meta_data.get("world_name") or "World")
            game_view = GameView(
                seed=seed,
                world_name=world_name,
                save_data=save_payload,
                restore_runtime_state=is_dev_restore,
            )
            window.show_view(game_view)
            if is_dev_restore and isinstance(state_data, dict):
                overlay_chain: list[str] = []
                raw_chain = state_data.get("active_overlay_views")
                if isinstance(raw_chain, list):
                    overlay_chain = [entry.strip() for entry in raw_chain if isinstance(entry, str) and entry.strip()]
                if not overlay_chain:
                    overlay_key = state_data.get("active_overlay_view")
                    if isinstance(overlay_key, str) and overlay_key.strip():
                        overlay_chain = [overlay_key.strip()]
                if not overlay_chain and state_data.get("active_view") == "game_menu":
                    # Rueckwaertskompatibel zu bestehenden Dev-Saves.
                    overlay_chain = ["game_menu"]
                if overlay_chain:
                    _restore_overlay_chain(game_view, overlay_chain)
            did_load = True
            print(f"[dev-load] restored {load_save_path}")
        except Exception as exc:
            print(f"[dev-load] failed ({load_save_path}): {exc}")

    if not did_load:
        window.show_view(StartMenuView())

    arcade.run()


GameWindow = GameView


if __name__ == "__main__":
    main()
