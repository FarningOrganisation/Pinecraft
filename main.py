"""Pinecraft — Milestone 3.

Dieses Projekt enthält jetzt ein einfaches Block- und Chunk-Modell mit
statischer Terrain-Erzeugung. Der Spieler bleibt weiterhin das zentrale
Bewegungselement, während die Welt als einfache, deterministische
Chunk-Struktur aufgebaut wird.
"""

import math
from pathlib import Path

import arcade
from arcade.gl import geometry as gl_geometry
from arcade.future.light import Light, LightLayer

from blocks import AIR, BLOCK_TEXTURES, get_block_light_opacity, is_block_skylight_surface
from dropped_item import DroppedItem
from hotbar import Hotbar
from inventory_ui import InventoryUI
from items import ITEM_TEXTURES, TORCH
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
        self.hotbar = Hotbar(self.player)
        self.inventory_ui = InventoryUI(self.player, SCREEN_WIDTH, SCREEN_HEIGHT)
        self.chunk_sprite_lists: dict[int, arcade.SpriteList] = {}
        self.chunk_sprite_maps: dict[int, dict[tuple[int, int], arcade.Sprite]] = {}
        self.camera = arcade.Camera2D()
        self.ui_camera = arcade.Camera2D()
        self.physics = AABBPhysics(self.world)
        self.light_layer = LightLayer(self.width, self.height)
        self.light_layer.set_background_color((0, 0, 0, 0))
        self.player_torch_light = Light(0.0, 0.0, radius=0.0, color=(255, 255, 230), mode="soft")
        self.light_layer.add(self.player_torch_light)
        self.placed_torch_lights: dict[tuple[int, int], Light] = {}
        self.sky_shader_program = self.ctx.program(
            vertex_shader="""
                #version 330
                in vec2 in_vert;
                in vec2 in_uv;
                out vec2 uv;

                void main() {
                    uv = in_uv;
                    gl_Position = vec4(in_vert, 0.0, 1.0);
                }
            """,
            fragment_shader="""
                #version 330
                in vec2 uv;
                out vec4 fragColor;

                uniform float u_day_factor;
                uniform float u_time_of_day;

                float triangle_window(float center, float width, float x) {
                    return max(0.0, 1.0 - abs(x - center) / width);
                }

                void main() {
                    float y = clamp(uv.y, 0.0, 1.0);

                    vec3 night_horizon = vec3(0.08, 0.13, 0.24);
                    vec3 night_zenith = vec3(0.03, 0.06, 0.16);
                    vec3 day_horizon = vec3(0.78, 0.92, 1.00);
                    vec3 day_zenith = vec3(0.40, 0.73, 1.00);
                    vec3 dusk_tint = vec3(1.00, 0.55, 0.32);

                    vec3 horizon = mix(night_horizon, day_horizon, pow(u_day_factor, 0.85));
                    vec3 zenith = mix(night_zenith, day_zenith, pow(u_day_factor, 0.92));

                    float vertical = smoothstep(0.0, 1.0, y);
                    vec3 color = mix(horizon, zenith, vertical);

                    float twilight = max(
                        triangle_window(0.25, 0.16, u_time_of_day),
                        triangle_window(0.75, 0.16, u_time_of_day)
                    );
                    float horizon_band = pow(1.0 - vertical, 1.9);
                    float twilight_strength = twilight * (0.45 + 0.55 * (1.0 - u_day_factor));
                    color = mix(color, dusk_tint, twilight_strength * horizon_band * 0.62);

                    fragColor = vec4(color, 1.0);
                }
            """,
        )
        self.sky_quad = gl_geometry.quad_2d_fs()
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
        self.day_length_seconds = 300.0
        self.time_of_day = 0.50
        self.sun_radius = 34
        self.moon_radius = 26
        self.celestial_size_px = 35
        sky_textures_dir = Path(__file__).resolve().parent / "assets" / "textures" / "sky"
        self.sun_sprite: arcade.Sprite | None = None
        self.moon_sprite: arcade.Sprite | None = None

        sun_path = sky_textures_dir / "sun.png"
        if sun_path.exists():
            self.sun_sprite = arcade.Sprite(str(sun_path), scale=1.0)
            self.sun_sprite.width = self.celestial_size_px
            self.sun_sprite.height = self.celestial_size_px

        moon_path = sky_textures_dir / "moon.png"
        if moon_path.exists():
            self.moon_sprite = arcade.Sprite(str(moon_path), scale=1.0)
            self.moon_sprite.width = self.celestial_size_px
            self.moon_sprite.height = self.celestial_size_px

    @staticmethod
    def _lerp_color(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
        """Lineare Interpolation zwischen zwei RGB-Farben."""
        t = max(0.0, min(1.0, t))
        return (
            int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t),
        )

    def _day_factor(self) -> float:
        """0.0 = Mitternacht, 1.0 = Mittag."""
        return (math.cos(2.0 * math.pi * (self.time_of_day - 0.5)) + 1.0) * 0.5

    def _sky_color(self) -> tuple[int, int, int, int]:
        """Kontinuierliche Himmelsfarbe mit Sunrise/Sunset-Akzent."""
        t = self.time_of_day
        day_factor = self._day_factor()

        night = (5, 11, 29)
        day = (82, 168, 255)
        sunset = (255, 150, 96)

        base = self._lerp_color(night, day, day_factor**0.86)

        twilight_a = max(0.0, 1.0 - abs(t - 0.25) / 0.16)
        twilight_b = max(0.0, 1.0 - abs(t - 0.75) / 0.16)
        twilight = max(twilight_a, twilight_b)

        twilight_strength = min(1.0, twilight * (0.45 + 0.55 * (1.0 - day_factor)))
        rgb = self._lerp_color(base, sunset, twilight_strength * 0.78)
        return rgb[0], rgb[1], rgb[2], 255

    def _is_player_underground(self) -> bool:
        """Die Höhlen-Erkennung wurde verworfen; die Dunkelheit kommt aus Nachbar-Block-Tiefe statt der Welt-Logik."""
        return False

    def _ambient_color(self) -> tuple[int, int, int]:
        """Am Tag darf das Ambient-Lighting nicht dunkler machen; nur Nacht und Dämmerung färben die Szene."""
        day_factor = self._day_factor()
        if day_factor >= 0.25:
            return (255, 255, 255)
        if day_factor > 0.10:
            return self._lerp_color((80, 90, 120), (255, 255, 255), (day_factor - 0.10) / (0.25 - 0.10))
        return (55, 66, 95)

    def _draw_sky_shader(self):
        """Zeichnet den dynamischen Himmel per Fullscreen-Fragment-Shader."""
        self.sky_shader_program["u_day_factor"] = float(self._day_factor())
        self.sky_shader_program["u_time_of_day"] = float(self.time_of_day)
        self.sky_quad.render(self.sky_shader_program)

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

    def _sync_torch_lights(self):
        """Synchronisiert Spieler- und Welt-Fackellichter mit dem aktuellen Zustand."""
        torch_daylight_scale = self._torch_daylight_multiplier(self.player.center_x, self.player.center_y)

        if self._is_torch_equipped():
            light_pos = self.player.get_equipped_light_source_position()
            if light_pos is None:
                light_pos = (self.player.center_x, self.player.center_y + self.player.height * 0.10)
            self.player_torch_light.position = light_pos
            self.player_torch_light.radius = 150.0 * torch_daylight_scale
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
                light = Light(light_x, light_y, radius=radius, color=(255, 255, 230), mode="soft")
                self.light_layer.add(light)
                self.placed_torch_lights[tile_pos] = light
            else:
                light.position = (light_x, light_y)
                light.radius = radius

    def _torch_daylight_multiplier(self, world_x: float, world_y: float) -> float:
        """Torch visibility fades almost to zero in bright daylight and rises again toward dusk/night."""
        day_factor = self._day_factor()
        if day_factor >= 0.72:
            return 0.0
        if day_factor <= 0.15:
            return 1.0
        return max(0.0, 1.0 - ((day_factor - 0.15) / (0.72 - 0.15)) * 0.98)

    def _has_sky_access(self, world_x: float, world_y: float, max_scan: int = 18) -> bool:
        """Veraltet: Die Höhlen-Erkennung wurde entfernt; Tiefenschattierung basiert auf Nachbarn."""
        return True

    def _get_visible_tile_x_range(self, margin_tiles: int = 2) -> tuple[int, int]:
        """Berechnet den horizontal sichtbaren Tile-Bereich der Kamera."""
        half_w = self.width / 2
        min_tile_x = int((self.camera.position[0] - half_w) // TILE_SIZE) - margin_tiles
        max_tile_x = int((self.camera.position[0] + half_w) // TILE_SIZE) + margin_tiles
        return min_tile_x, max_tile_x

    def _column_surface_and_shadow(self, tile_x: int) -> tuple[int, float]:
        """Liefert natürliche Oberfläche und Zusatzschatten durch Objekte mit Luftspalt darüber."""
        surface_y = -1
        for y in range(WORLD_HEIGHT - 1, -1, -1):
            block_id = self.world.get_block(tile_x, y, generate_if_missing=False)
            if get_block_light_opacity(block_id) <= 0.0:
                continue
            if is_block_skylight_surface(block_id):
                surface_y = y
                break

        if surface_y < 0:
            return -1, 0.0

        shadow_bonus = 0.0
        for y in range(surface_y + 2, WORLD_HEIGHT):
            block_id = self.world.get_block(tile_x, y, generate_if_missing=False)
            opacity = get_block_light_opacity(block_id)
            if opacity <= 0.0:
                continue
            gap = y - (surface_y + 1)
            shadow_bonus += opacity * (0.64 / (1.0 + gap * 0.22))

        return surface_y, min(2.4, shadow_bonus)

    def _torch_shadow_positions(self) -> list[tuple[int, int]]:
        """Positionsliste aller Lichtquellen, die die Dunkelheitsmaske aufhellen sollen."""
        positions = list(self.placed_torch_lights.keys())

        if self._is_torch_equipped():
            player_light_pos = self.player.get_equipped_light_source_position()
            if player_light_pos is not None:
                positions.append((int(player_light_pos[0] // TILE_SIZE), int(player_light_pos[1] // TILE_SIZE)))

        return positions

    def _draw_underground_darkness_overlay(self):
        """Zeichnet die Tiefe anhand der Nachbar-Block-Struktur; keine globale Höhlen-Erkennung mehr."""
        min_tile_x, max_tile_x = self._get_visible_tile_x_range(margin_tiles=2)
        min_tile_y, max_tile_y = self._get_visible_tile_range(margin_tiles=1)

        if min_tile_y > max_tile_y:
            return

        visible_left = min_tile_x * TILE_SIZE
        visible_right = (max_tile_x + 1) * TILE_SIZE
        visible_bottom = min_tile_y * TILE_SIZE
        visible_top = (max_tile_y + 1) * TILE_SIZE

        base_color = (18, 14, 18, 90)
        arcade.draw_lrbt_rectangle_filled(visible_left, visible_right, visible_bottom, visible_top, base_color)

        torch_positions = self._torch_shadow_positions()

        lateral_scan = 9
        scan_min_x = min_tile_x - lateral_scan
        scan_max_x = max_tile_x + lateral_scan
        surface_info: dict[int, tuple[int, float]] = {}
        for tile_x in range(scan_min_x, scan_max_x + 1):
            surface_info[tile_x] = self._column_surface_and_shadow(tile_x)

        column_shadow_strength: dict[int, float] = {}
        for tile_x in range(scan_min_x, scan_max_x + 1):
            local_shadow = surface_info.get(tile_x, (-1, 0.0))[1]
            neighbor_total = 0.0
            neighbor_count = 0
            for nx in range(tile_x - 2, tile_x + 3):
                neighbor_total += surface_info.get(nx, (-1, 0.0))[1]
                neighbor_count += 1

            neighbor_avg = neighbor_total / max(1, neighbor_count)
            canopy_weight = max(0.0, min(1.0, (neighbor_avg - 0.22) / 0.85))
            column_shadow_strength[tile_x] = local_shadow * canopy_weight

        day_factor = self._day_factor()
        darkness_scale = 0.14 + (1.0 - day_factor) * 1.05

        if day_factor >= 0.30:
            darkness_scale *= 0.15

        for tile_x in range(min_tile_x, max_tile_x + 1):
            for tile_y in range(min_tile_y, max_tile_y + 1):
                min_effective_depth = float("inf")

                for dx in range(-lateral_scan, lateral_scan + 1):
                    source_x = tile_x + dx
                    source_surface_y, shadow_bonus = surface_info.get(source_x, (-1, 0.0))
                    vertical_depth = max(0.0, (source_surface_y + 1) - tile_y)
                    if vertical_depth > 0.0:
                        shadow_strength = column_shadow_strength.get(source_x, shadow_bonus)
                        shadow_depth_factor = min(1.0, vertical_depth / 6.0)
                        vertical_depth += shadow_strength * shadow_depth_factor
                    lateral_penalty = abs(dx) * 2.0
                    effective_depth = vertical_depth + lateral_penalty
                    if effective_depth < min_effective_depth:
                        min_effective_depth = effective_depth

                if min_effective_depth <= 0:
                    continue

                depth_after_threshold = max(0.0, min_effective_depth - 1.0)
                alpha = int(min(220, (depth_after_threshold**1.22) * 10.0 * darkness_scale))

                if day_factor >= 0.65:
                    alpha = max(0, alpha // 10)

                torch_boost = 0.0
                for torch_tile_x, torch_tile_y in torch_positions:
                    torch_center_x = (torch_tile_x + 0.5) * TILE_SIZE
                    torch_center_y = (torch_tile_y + 0.5) * TILE_SIZE
                    px = (tile_x + 0.5) * TILE_SIZE
                    py = (tile_y + 0.5) * TILE_SIZE
                    dist = math.hypot(px - torch_center_x, py - torch_center_y)
                    if dist <= 180.0:
                        torch_boost = max(torch_boost, 1.0 - dist / 180.0)

                if torch_boost > 0.0:
                    alpha = max(0, int(alpha * (1.0 - min(0.96, torch_boost * 1.1))))

                if alpha < 6:
                    continue

                left = tile_x * TILE_SIZE
                bottom = tile_y * TILE_SIZE
                right = left + TILE_SIZE
                top = bottom + TILE_SIZE
                arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, (0, 0, 0, alpha))

    def _celestial_position(self, progress: float) -> tuple[float, float]:
        """Bildschirmposition auf einer echten Ellipsen-Halbbahn (rechts nach links)."""
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
        """Zeichnet einen günstigen Pseudo-Bloom über mehrere weiche Ringe."""
        ring_count = 4
        for i in range(ring_count, 0, -1):
            t = i / ring_count
            radius = core_radius + (18.0 * strength) * (1.0 + t * 1.8)
            alpha = int(22 * strength * (t**1.7))
            if alpha <= 0:
                continue
            arcade.draw_circle_filled(x, y, radius, (glow_color[0], glow_color[1], glow_color[2], alpha))

    def _draw_celestials(self):
        """Zeichnet Sonne und Mond von rechts nach links über den Himmel."""
        sun_progress = (self.time_of_day - 0.25) / 0.5
        if 0.0 <= sun_progress <= 1.0:
            sun_x, sun_y = self._celestial_position(sun_progress)
            if self.sun_sprite is not None:
                self.sun_sprite.center_x = sun_x
                self.sun_sprite.center_y = sun_y
                self.sun_sprite.color = (255, 255, 255)
                self.sun_sprite.alpha = 255
                arcade.draw_sprite(self.sun_sprite)
            else:
                arcade.draw_circle_filled(sun_x, sun_y, self.sun_radius, (255, 236, 130, 255))

        moon_progress: float | None = None
        if self.time_of_day >= 0.75:
            moon_progress = (self.time_of_day - 0.75) / 0.5
        elif self.time_of_day < 0.25:
            moon_progress = (self.time_of_day + 0.25) / 0.5

        if moon_progress is not None:
            moon_x, moon_y = self._celestial_position(moon_progress)
            self._draw_glow_orb(moon_x, moon_y, self.moon_radius, (170, 208, 255), strength=0.78)
            if self.moon_sprite is not None:
                self.moon_sprite.center_x = moon_x
                self.moon_sprite.center_y = moon_y
                self.moon_sprite.alpha = 255
                arcade.draw_sprite(self.moon_sprite)
            else:
                arcade.draw_circle_filled(moon_x, moon_y, self.moon_radius, (214, 226, 255, 235))
                arcade.draw_circle_filled(moon_x + 7, moon_y + 2, self.moon_radius - 7, (12, 20, 42, 220))

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
        self.frame_count = 0
        self.world = World()
        self.player = Player(world=self.world)
        self.player.center_x = SCREEN_WIDTH / 2
        ground_y = self.world.get_ground_top(int(self.player.center_x))
        self.player.center_y = ground_y + self.player.height / 2
        self.player.change_x = 0.0
        self.player.change_y = 0.0
        self.player.on_ground = True
        self.player_sprite_list = arcade.SpriteList()
        self.player_sprite_list.append(self.player)
        self.mining_sprite_list = arcade.SpriteList()
        self.mining_sprite_list.append(self.player.mining_animation)
        self.dropped_item_sprite_list = arcade.SpriteList()
        self.dropped_items = []
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

    def on_update(self, delta_time: float):
        """Wird regelmäßig pro Frame aufgerufen."""
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

        physics_delta = min(delta_time, 1 / 30)
        self.physics.update(self.player, physics_delta)
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
            self.player.draw_held_item(layer="back")
            self.player_sprite_list.draw()
            self.player.draw_held_item(layer="front")
            self.mining_sprite_list.draw()
            self._draw_underground_darkness_overlay()

        self.light_layer.draw(ambient_color=self._ambient_color())

        self.ui_camera.use()
        self.hotbar.draw()
        self.inventory_ui.draw()
        self.fps_text.y = self.height - 16
        self.fps_text.draw()

    def on_key_press(self, symbol: int, modifiers: int):
        """Reagiert auf Tastatureingaben."""
        ctrl_down = bool(modifiers & getattr(arcade.key, "MOD_CTRL", 0))
        if ctrl_down and symbol == arcade.key.D:
            self.time_of_day = 0.50
            return

        if ctrl_down and symbol == arcade.key.N:
            self.time_of_day = 0.00
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
        self.mouse_screen_x = x
        self.mouse_screen_y = y

        if self.inventory_ui.visible:
            self.inventory_ui.handle_click(x, y, button, modifiers)
            return

        if button == arcade.MOUSE_BUTTON_LEFT:
            self.left_mouse_down = True
            target = self._get_block_from_mouse(x, y)
            if target is None:
                self.pending_mine_target = None
                return

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
