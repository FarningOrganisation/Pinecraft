"""Lighting and sky rendering helpers for the game."""

from array import array
import math
import random
import time

import arcade
from arcade.future.light import Light
from arcade.gl import geometry as gl_geometry

from blocks import AIR, get_block_light_opacity, is_block_skylight_surface
from items import TORCH
from paths import textures_dir
from settings import TILE_SIZE, WORLD_HEIGHT
from world_generation import SEA_LEVEL

CELESTIAL_HIDE_BELOW_SEA_TILES = 10
MAX_SHADER_TORCH_LIGHTS = 32
SHADER_TORCH_RADIUS = 210.0


class LightingSystem:
    """Encapsulates sky, daylight, cave darkness and torch lighting logic."""

    def __init__(self, window):
        self.window = window
        self.torch_light_color = (255, 190, 100)
        self.use_cpu_underground_overlay_debug = False
        self.surface_map_margin_tiles = 4

        self.profile_cpu_overlay_ms = 0.0
        self.profile_surface_map_update_ms = 0.0
        self.profile_shader_overlay_ms = 0.0
        self.profile_moon_light_enabled = False
        self.profile_moon_light_world_pos: tuple[float, float] = (0.0, 0.0)
        self.profile_moon_light_radius = 0.0
        self.profile_moon_light_strength = 0.0

        self.window.light_layer.set_background_color((0, 0, 0, 0))
        self.player_torch_light = Light(0.0, 0.0, radius=0.0, color=self.torch_light_color, mode="soft")
        self.window.light_layer.add(self.player_torch_light)
        self.placed_torch_lights: dict[tuple[int, int], Light] = {}

        self.sky_shader_program = self.window.ctx.program(
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
                uniform float u_underground;

                float triangle_window(float center, float width, float x) {
                    return max(0.0, 1.0 - abs(x - center) / width);
                }

                float hash21(vec2 p) {
                    p = fract(p * vec2(123.34, 345.45));
                    p += dot(p, p + 34.345);
                    return fract(p.x * p.y);
                }

                void main() {
                    float y = clamp(uv.y, 0.0, 1.0);

                    vec3 night_horizon = vec3(0.08, 0.13, 0.24);
                    vec3 night_zenith = vec3(0.03, 0.06, 0.16);
                    vec3 day_horizon = vec3(0.86, 0.96, 1.00);
                    vec3 day_zenith = vec3(0.62, 0.86, 1.00);
                    vec3 cave_horizon = vec3(0.24, 0.16, 0.11);
                    vec3 cave_zenith = vec3(0.38, 0.24, 0.16);
                    vec3 dusk_tint = vec3(1.00, 0.55, 0.32);

                    vec3 horizon = mix(night_horizon, day_horizon, pow(u_day_factor, 0.85));
                    vec3 zenith = mix(night_zenith, day_zenith, pow(u_day_factor, 0.92));
                    horizon = mix(horizon, cave_horizon, u_underground);
                    zenith = mix(zenith, cave_zenith, u_underground);

                    float vertical = smoothstep(0.0, 1.0, y);
                    vec3 color = mix(horizon, zenith, vertical);

                    float twilight = max(
                        triangle_window(0.25, 0.16, u_time_of_day),
                        triangle_window(0.75, 0.16, u_time_of_day)
                    );
                    float horizon_band = pow(1.0 - vertical, 1.9);
                    float twilight_strength = twilight * (0.45 + 0.55 * (1.0 - u_day_factor));
                    color = mix(color, dusk_tint, twilight_strength * horizon_band * 0.62);

                    // Dezente, kleine Sterne nur nachts und vor allem im oberen Himmel.
                    float night_strength = pow(max(0.0, 1.0 - u_day_factor), 1.55);
                    vec2 star_uv = uv * vec2(210.0, 130.0);
                    vec2 star_cell = floor(star_uv);
                    vec2 star_local = fract(star_uv) - 0.5;
                    float star_seed = hash21(star_cell);
                    float star_mask = step(0.9945, star_seed);
                    float star_dist = length(star_local);
                    float star_core = (1.0 - smoothstep(0.02, 0.11, star_dist)) * star_mask;
                    float twinkle = 0.72 + 0.28 * sin((u_time_of_day * 6.2831853 * 8.0) + star_seed * 40.0);
                    float star_visibility = night_strength * pow(y, 1.7) * (1.0 - min(1.0, u_underground * 1.25));
                    color += vec3(0.92, 0.95, 1.0) * star_core * twinkle * star_visibility * 0.85;

                    fragColor = vec4(color, 1.0);
                }
            """,
        )
        self.sky_quad = gl_geometry.quad_2d_fs()

        self.cave_depth_shader_program = self.window.ctx.program(
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

                uniform sampler2D u_surface_tex;
                uniform float u_surface_min_x;
                uniform float u_surface_span;
                uniform float u_camera_world_x;
                uniform float u_camera_world_y;
                uniform float u_screen_width;
                uniform float u_screen_height;
                uniform float u_tile_size;
                uniform float u_day_factor;
                uniform int u_light_count;
                uniform vec2 u_light_positions[32];
                uniform float u_light_radii[32];
                uniform int u_moon_light_enabled;
                uniform vec2 u_moon_light_position;
                uniform float u_moon_light_radius;
                uniform float u_moon_light_strength;
                uniform vec3 u_moon_light_color;

                float sample_surface_y(float world_tile_x) {
                    float col = clamp(world_tile_x - u_surface_min_x, 0.0, u_surface_span - 1.0);
                    float su = (col + 0.5) / u_surface_span;
                    return texture(u_surface_tex, vec2(su, 0.5)).r;
                }

                void main() {
                    float world_x = u_camera_world_x + (uv.x - 0.5) * u_screen_width;
                    float world_y = u_camera_world_y + (uv.y - 0.5) * u_screen_height;
                    float world_tile_x = world_x / u_tile_size;

                    // Mehrfach-Samples glätten Übergänge an Kanten/Höhleneingängen.
                    float s0 = sample_surface_y(world_tile_x - 2.0);
                    float s1 = sample_surface_y(world_tile_x - 1.0);
                    float s2 = sample_surface_y(world_tile_x);
                    float s3 = sample_surface_y(world_tile_x + 1.0);
                    float s4 = sample_surface_y(world_tile_x + 2.0);
                    float surface_y = (s0 * 0.11) + (s1 * 0.22) + (s2 * 0.34) + (s3 * 0.22) + (s4 * 0.11);

                    float depth = max(0.0, surface_y - world_y);
                    float cave_darkness = smoothstep(56.0, 520.0, depth);
                    float day_strength = mix(0.72, 0.96, u_day_factor);
                    cave_darkness = clamp(cave_darkness * day_strength, 0.0, 0.92);
                    float local_light_receiver = smoothstep(10.0, 70.0, depth);

                    // Nacht heller, Twilight-Übergang breiter und weicher.
                    float ambient = mix(0.48, 1.0, pow(clamp(u_day_factor, 0.0, 1.0), 1.55));
                    float base_light = ambient * (1.0 - cave_darkness);

                    vec2 world_pos = vec2(world_x, world_y);
                    float torch_light = 0.0;
                    for (int i = 0; i < 32; i++) {
                        if (i >= u_light_count) {
                            break;
                        }
                        float radius = max(1.0, u_light_radii[i]);
                        float dist = distance(world_pos, u_light_positions[i]);
                        float falloff = 1.0 - smoothstep(radius * 0.10, radius, dist);
                        torch_light += falloff * 0.92 * local_light_receiver;
                    }

                    float moon_light = 0.0;
                    if (u_moon_light_enabled > 0) {
                        float md = distance(world_pos, u_moon_light_position);
                        moon_light = (1.0 - smoothstep(u_moon_light_radius * 0.04, u_moon_light_radius, md)) * u_moon_light_strength * local_light_receiver;
                    }

                    vec3 final_light = vec3(base_light + torch_light);
                    final_light += u_moon_light_color * moon_light;
                    final_light = clamp(final_light, vec3(0.0), vec3(1.0));
                    // Src-Farbe ist ein Lichtfaktor; DST_COLOR-Blending multipliziert
                    // damit die bereits gezeichnete Weltfarbe.
                    fragColor = vec4(final_light, 1.0);
                }
            """,
        )
        self.cave_depth_shader_program["u_surface_tex"] = 0

        self._surface_height_texture = self.window.ctx.texture((1, 1), components=1, data=array("f", [0.0]).tobytes(), dtype="f4")
        self._surface_height_texture.filter = (self.window.ctx.LINEAR, self.window.ctx.LINEAR)
        self._surface_min_tile_x = 0
        self._surface_max_tile_x = 0
        self._surface_map_dirty = True

        self.sun_sprite: arcade.Sprite | None = None
        self.moon_sprite: arcade.Sprite | None = None
        sky_textures_dir = textures_dir("sky")

        sun_path = sky_textures_dir / "sun.png"
        if sun_path.exists():
            self.sun_sprite = arcade.Sprite(str(sun_path), scale=1.0)
            self.sun_sprite.width = 35
            self.sun_sprite.height = 35

        moon_path = sky_textures_dir / "moon.png"
        if moon_path.exists():
            self.moon_sprite = arcade.Sprite(str(moon_path), scale=1.0)
            self.moon_sprite.width = 35
            self.moon_sprite.height = 35

        # Deterministische Sternkarte im Bildschirmraum (normierte Koordinaten).
        rng = random.Random(24681357)
        self._star_field: list[tuple[float, float, float, float]] = []
        for _ in range(180):
            sx = rng.random()
            sy = rng.random()
            if sy < 0.30:
                continue
            size = 0.7 + rng.random() * 1.2
            phase = rng.random() * math.tau
            self._star_field.append((sx, sy, size, phase))

    @staticmethod
    def lerp_color(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
        """Lineare Interpolation zwischen zwei RGB-Farben."""
        t = max(0.0, min(1.0, t))
        return (
            int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t),
        )

    def day_factor(self) -> float:
        """0.0 = Mitternacht, 1.0 = Mittag."""
        return (math.cos(2.0 * math.pi * (self.window.time_of_day - 0.5)) + 1.0) * 0.5

    def sky_color(self) -> tuple[int, int, int, int]:
        """Kontinuierliche Himmelsfarbe mit Sunrise/Sunset-Akzent."""
        t = self.window.time_of_day
        day_factor = self.day_factor()

        night = (5, 11, 29)
        day = (82, 168, 255)
        sunset = (255, 150, 96)

        base = self.lerp_color(night, day, day_factor**0.86)

        twilight_a = max(0.0, 1.0 - abs(t - 0.25) / 0.16)
        twilight_b = max(0.0, 1.0 - abs(t - 0.75) / 0.16)
        twilight = max(twilight_a, twilight_b)

        twilight_strength = min(1.0, twilight * (0.45 + 0.55 * (1.0 - day_factor)))
        rgb = self.lerp_color(base, sunset, twilight_strength * 0.78)
        return rgb[0], rgb[1], rgb[2], 255

    def is_sky_lit_air(self, tile_x: int, tile_y: int, max_scan: int = 18) -> bool:
        """True, wenn dieser Luftblock mit einer offenen Sky-Säule verbunden ist."""
        if self.window.world.get_block(tile_x, tile_y, generate_if_missing=False) != AIR:
            return False

        for y in range(tile_y + 1, min(WORLD_HEIGHT, tile_y + max_scan + 1)):
            if self.window.world.get_block(tile_x, y, generate_if_missing=False) != AIR:
                return False
        return True

    def _column_top_occluder_y(self, tile_x: int) -> int:
        """Oberste lichtblockierende Tile in einer Spalte; -1 falls nach oben offen."""
        for y in range(WORLD_HEIGHT - 1, -1, -1):
            block_id = self.window.world.get_block(tile_x, y, generate_if_missing=False)
            if get_block_light_opacity(block_id) > 0.0:
                return y
        return -1

    def sky_background_blend(self) -> float:
        """0 = normale Sky-Farbe, 1 = tiefe Höhle; Abstand zur nächsten Open-Air-Säule bestimmt den Übergang."""
        player_tile_x = int(self.window.player.center_x // TILE_SIZE)
        player_tile_y = int(self.window.player.center_y // TILE_SIZE)
        search_radius = 12
        nearest_sky_distance = float("inf")

        top_occluder_by_x: dict[int, int] = {}
        for tile_x in range(player_tile_x - search_radius, player_tile_x + search_radius + 1):
            top_occluder_by_x[tile_x] = self._column_top_occluder_y(tile_x)

        for ox in range(-search_radius, search_radius + 1):
            for oy in range(-search_radius, search_radius + 1):
                tile_x = player_tile_x + ox
                tile_y = player_tile_y + oy
                if tile_y < 0 or tile_y >= WORLD_HEIGHT:
                    continue
                if self.window.world.get_block(tile_x, tile_y, generate_if_missing=False) != AIR:
                    continue
                if tile_y <= top_occluder_by_x.get(tile_x, -1):
                    continue
                dist = math.hypot(ox, oy)
                if dist < nearest_sky_distance:
                    nearest_sky_distance = dist

        if math.isinf(nearest_sky_distance):
            return 1.0

        return max(0.0, min(1.0, (nearest_sky_distance - 2.0) / 11.0))

    def ambient_color(self) -> tuple[int, int, int]:
        """Tagsüber neutral/weiß; bei Dämmerung/Nacht weicher und dunkler."""
        day_factor = self.day_factor()
        if day_factor >= 0.60:
            return (255, 255, 255)

        # Breiter Twilight-Bereich: langsamerer Lichtwechsel um Sunrise/Sunset.
        if day_factor > 0.20:
            t = (day_factor - 0.20) / (0.60 - 0.20)
            return self.lerp_color((36, 43, 62), (255, 255, 255), t)

        # Nacht etwas heller als zuvor.
        return (58, 68, 102)

    def draw_sky_shader(self):
        """Zeichnet den dynamischen Himmel per Fullscreen-Fragment-Shader."""
        self.sky_shader_program["u_day_factor"] = float(self.day_factor())
        self.sky_shader_program["u_time_of_day"] = float(self.window.time_of_day)
        self.sky_shader_program["u_underground"] = float(self.sky_background_blend())
        self.sky_quad.render(self.sky_shader_program)

    def notify_world_block_changes(self, changed_blocks: list[tuple[int, int, int, int]]) -> None:
        """Markiert die Surface-Map als dirty, wenn relevante sichtbare Spalten geändert wurden."""
        if not changed_blocks:
            return

        if self._surface_min_tile_x > self._surface_max_tile_x:
            self._surface_map_dirty = True
            return

        guard = self.surface_map_margin_tiles + 2
        min_x = self._surface_min_tile_x - guard
        max_x = self._surface_max_tile_x + guard
        for world_x, _y, _old_block, _new_block in changed_blocks:
            if min_x <= world_x <= max_x:
                self._surface_map_dirty = True
                return

    def _update_surface_height_texture_if_needed(self) -> None:
        """Aktualisiert die Surface-Height-Texture nur bei neuem Kamera-X-Bereich oder dirty-Flag."""
        min_tile_x, max_tile_x = self.window._get_visible_tile_x_range(margin_tiles=self.surface_map_margin_tiles)
        range_changed = min_tile_x != self._surface_min_tile_x or max_tile_x != self._surface_max_tile_x
        if not range_changed and not self._surface_map_dirty:
            return

        t0 = time.perf_counter()
        self._surface_min_tile_x = min_tile_x
        self._surface_max_tile_x = max_tile_x
        width = max(1, max_tile_x - min_tile_x + 1)

        values = array("f")
        for tile_x in range(min_tile_x, max_tile_x + 1):
            # Echte Spaltenoberfläche aus Blockstruktur statt Terrain-Funktionswert.
            surface_tile_y = -1
            for y in range(WORLD_HEIGHT - 1, -1, -1):
                block_id = self.window.world.get_block(tile_x, y, generate_if_missing=False)
                if get_block_light_opacity(block_id) <= 0.0:
                    continue
                if is_block_skylight_surface(block_id):
                    surface_tile_y = y
                    break

            if surface_tile_y < 0:
                surface_tile_y = self._column_top_occluder_y(tile_x)
            if surface_tile_y < 0:
                surface_tile_y = SEA_LEVEL

            values.append(float((surface_tile_y + 1) * TILE_SIZE))

        data = values.tobytes() if values else array("f", [0.0]).tobytes()
        if self._surface_height_texture.size[0] != width:
            old_texture = self._surface_height_texture
            release_fn = getattr(old_texture, "release", None)
            if callable(release_fn):
                release_fn()
            else:
                delete_fn = getattr(old_texture, "delete", None)
                if callable(delete_fn):
                    delete_fn()
            self._surface_height_texture = self.window.ctx.texture((width, 1), components=1, data=data, dtype="f4")
            self._surface_height_texture.filter = (self.window.ctx.LINEAR, self.window.ctx.LINEAR)
        else:
            self._surface_height_texture.write(data)

        self._surface_map_dirty = False
        self.profile_surface_map_update_ms = (time.perf_counter() - t0) * 1000.0

    def _is_torch_equipped(self) -> bool:
        """True, wenn der aktuell ausgewählte Hotbar-Slot eine Fackel enthält."""
        return self.window._is_torch_equipped()

    def torch_daylight_multiplier(self, world_x: float, world_y: float) -> float:
        """Torch visibility fades almost to zero in bright daylight and rises again toward dusk/night."""
        day_factor = self.day_factor()
        tile_x = int(world_x // TILE_SIZE)
        tile_y = int(world_y // TILE_SIZE)
        has_sky_access = self.is_sky_lit_air(tile_x, tile_y, max_scan=24)

        # Bei offenem Himmel tagsüber kein Torch-Effekt.
        if has_sky_access:
            if day_factor >= 0.60:
                return 0.0
            if day_factor <= 0.25:
                return 1.0
            return max(0.0, 1.0 - (day_factor - 0.25) / (0.60 - 0.25))

        # Unterirdisch darf Torch auch tagsüber sichtbar bleiben.
        if day_factor <= 0.15:
            return 1.0
        if day_factor >= 0.90:
            return 0.35
        return max(0.35, 1.0 - ((day_factor - 0.15) / (0.90 - 0.15)) * 0.65)

    def _torch_shadow_positions(self) -> list[tuple[int, int]]:
        """Positionsliste aller Lichtquellen, die die Dunkelheitsmaske aufhellen sollen."""
        positions = list(self.placed_torch_lights.keys())

        if self.window._is_torch_equipped():
            player_light_pos = self.window.player.get_equipped_light_source_position()
            if player_light_pos is not None:
                positions.append((int(player_light_pos[0] // TILE_SIZE), int(player_light_pos[1] // TILE_SIZE)))

        return positions

    def _column_surface_and_shadow(self, tile_x: int) -> tuple[int, float]:
        """Liefert natürliche Oberfläche und Zusatzschatten durch Objekte mit Luftspalt darüber."""
        surface_y = -1
        for y in range(WORLD_HEIGHT - 1, -1, -1):
            block_id = self.window.world.get_block(tile_x, y, generate_if_missing=False)
            if get_block_light_opacity(block_id) <= 0.0:
                continue
            if is_block_skylight_surface(block_id):
                surface_y = y
                break

        if surface_y < 0:
            return -1, 0.0

        shadow_bonus = 0.0
        for y in range(surface_y + 2, WORLD_HEIGHT):
            block_id = self.window.world.get_block(tile_x, y, generate_if_missing=False)
            opacity = get_block_light_opacity(block_id)
            if opacity <= 0.0:
                continue
            gap = y - (surface_y + 1)
            shadow_bonus += opacity * (0.92 / (1.0 + gap * 0.18))

        return surface_y, min(3.4, shadow_bonus)

    def _compute_connected_sky_light(
        self,
        min_tile_x: int,
        max_tile_x: int,
        min_tile_y: int,
        max_tile_y: int,
    ) -> dict[tuple[int, int], float]:
        """Propagiert Tageslicht durch zusammenhängende Luftblöcke im sichtbaren Bereich."""
        from collections import deque

        sky_light: dict[tuple[int, int], float] = {}
        queue: deque[tuple[tuple[int, int], float]] = deque()

        top_occluder_by_x: dict[int, int] = {}
        for tile_x in range(min_tile_x, max_tile_x + 1):
            top_occluder_by_x[tile_x] = self._column_top_occluder_y(tile_x)

        for tile_x in range(min_tile_x, max_tile_x + 1):
            for tile_y in range(min_tile_y, max_tile_y + 1):
                if self.window.world.get_block(tile_x, tile_y, generate_if_missing=False) != AIR:
                    continue

                if tile_y > top_occluder_by_x.get(tile_x, -1):
                    cell = (tile_x, tile_y)
                    sky_light[cell] = 1.0
                    queue.append((cell, 1.0))

        while queue:
            (tile_x, tile_y), strength = queue.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                nx = tile_x + dx
                ny = tile_y + dy
                if nx < min_tile_x or nx > max_tile_x:
                    continue
                if ny < min_tile_y or ny > max_tile_y:
                    continue
                if self.window.world.get_block(nx, ny, generate_if_missing=False) != AIR:
                    continue

                weight = 0.82 if abs(dx) + abs(dy) == 1 else 0.63
                next_strength = strength * weight
                key = (nx, ny)
                if next_strength <= sky_light.get(key, 0.0):
                    continue
                sky_light[key] = next_strength
                queue.append((key, next_strength))

        return sky_light

    def _draw_underground_darkness_overlay_cpu(self):
        """Legacy CPU-Overlay fuer Debug/Profilvergleich."""
        min_tile_x, max_tile_x = self.window._get_visible_tile_x_range(margin_tiles=2)
        min_tile_y, max_tile_y = self.window._get_visible_tile_range(margin_tiles=1)

        if min_tile_y > max_tile_y:
            return

        visible_left = min_tile_x * TILE_SIZE
        visible_right = (max_tile_x + 1) * TILE_SIZE
        visible_bottom = min_tile_y * TILE_SIZE
        visible_top = (max_tile_y + 1) * TILE_SIZE

        base_color = (18, 14, 18, 90)
        arcade.draw_lrbt_rectangle_filled(visible_left, visible_right, visible_bottom, visible_top, base_color)

        torch_positions = self._torch_shadow_positions()
        connected_sky_light = self._compute_connected_sky_light(min_tile_x, max_tile_x, min_tile_y, max_tile_y)

        lateral_scan = 12
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
            for nx in range(tile_x - 4, tile_x + 5):
                neighbor_total += surface_info.get(nx, (-1, 0.0))[1]
                neighbor_count += 1

            neighbor_avg = neighbor_total / max(1, neighbor_count)
            canopy_weight = max(0.0, min(1.0, (neighbor_avg - 0.18) / 0.9))
            column_shadow_strength[tile_x] = local_shadow * canopy_weight

        day_factor = self.day_factor()
        darkness_scale = 0.52 + (1.0 - day_factor) * 1.2
        daylight_alpha_scale = 0.78 + (1.0 - day_factor) * 0.45
        daylight_alpha_scale = min(1.0, daylight_alpha_scale)

        for tile_x in range(min_tile_x, max_tile_x + 1):
            for tile_y in range(min_tile_y, max_tile_y + 1):
                min_effective_depth = float("inf")

                for dx in range(-3, 4):
                    for dy in range(-2, 3):
                        source_x = tile_x + dx
                        source_surface_y, shadow_bonus = surface_info.get(source_x, (-1, 0.0))
                        sample_y = tile_y + dy
                        vertical_depth = max(0.0, (source_surface_y + 1) - sample_y)
                        if vertical_depth > 0.0:
                            shadow_strength = column_shadow_strength.get(source_x, shadow_bonus)
                            shadow_depth_factor = min(1.0, vertical_depth / 6.0)
                            vertical_depth += shadow_strength * (1.8 + shadow_depth_factor)

                        diagonal_weight = 0.55 if abs(dx) > 0 and abs(dy) > 0 else 1.0
                        lateral_penalty = (abs(dx) + abs(dy) * 0.7) * 1.4 * diagonal_weight
                        effective_depth = vertical_depth + lateral_penalty
                        if effective_depth < min_effective_depth:
                            min_effective_depth = effective_depth

                if min_effective_depth <= 0:
                    continue

                depth_after_threshold = max(0.0, (min_effective_depth - 0.7) * 1.35)
                alpha = int(min(255, (depth_after_threshold**1.18) * 14.5 * darkness_scale))
                alpha = int(alpha * daylight_alpha_scale)

                if day_factor >= 0.38:
                    ambient_alpha = 0
                else:
                    ambient_exposure = max(0.0, 1.0 - min_effective_depth / 6.0)
                    ambient_alpha = int(ambient_exposure * (38.0 + day_factor * 46.0))

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
                    ambient_alpha = max(ambient_alpha, int(ambient_alpha * (1.0 - min(0.7, torch_boost * 0.9))))

                ambient_alpha = max(0, min(255, ambient_alpha))
                if ambient_alpha > 0:
                    ambient_color = self.ambient_color()
                    arcade.draw_lrbt_rectangle_filled(
                        tile_x * TILE_SIZE,
                        (tile_x + 1) * TILE_SIZE,
                        tile_y * TILE_SIZE,
                        (tile_y + 1) * TILE_SIZE,
                        (ambient_color[0], ambient_color[1], ambient_color[2], ambient_alpha),
                    )

                connected_light = connected_sky_light.get((tile_x, tile_y), 0.0)
                alpha = int(alpha * max(0.0, 1.0 - min(0.98, connected_light * 0.98)))

                if alpha < 6:
                    continue

                left = tile_x * TILE_SIZE
                bottom = tile_y * TILE_SIZE
                right = left + TILE_SIZE
                top = bottom + TILE_SIZE
                dark_alpha = max(0, alpha - int(ambient_alpha * 0.7))
                dark_alpha = max(0, min(255, dark_alpha))
                if dark_alpha > 0:
                    arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, (0, 0, 0, dark_alpha))

    def _draw_underground_darkness_overlay_shader(self):
        """GPU-Overlay: Cave-Dunkelheit aus Surface-Height-Texture im Fragment-Shader."""
        self._update_surface_height_texture_if_needed()
        surface_span = float(max(1, self._surface_max_tile_x - self._surface_min_tile_x + 1))

        def set_uniform_safe(name: str, value) -> bool:
            try:
                self.cave_depth_shader_program[name] = value
                return True
            except KeyError:
                # Manche Treiber optimieren ungenutzte Uniforms komplett heraus.
                return False

        torch_lights = self._collect_shader_torch_lights(MAX_SHADER_TORCH_LIGHTS)
        light_positions_flat: list[float] = [0.0] * (MAX_SHADER_TORCH_LIGHTS * 2)
        light_radii: list[float] = [0.0] * MAX_SHADER_TORCH_LIGHTS
        for i, (light_x, light_y, radius) in enumerate(torch_lights):
            light_positions_flat[i * 2] = light_x
            light_positions_flat[i * 2 + 1] = light_y
            light_radii[i] = radius

        set_uniform_safe("u_surface_min_x", float(self._surface_min_tile_x))
        set_uniform_safe("u_surface_span", surface_span)
        set_uniform_safe("u_camera_world_x", float(self.window.camera.position[0]))
        set_uniform_safe("u_camera_world_y", float(self.window.camera.position[1]))
        set_uniform_safe("u_screen_width", float(self.window.width))
        set_uniform_safe("u_screen_height", float(self.window.height))
        set_uniform_safe("u_tile_size", float(TILE_SIZE))
        set_uniform_safe("u_day_factor", float(self.day_factor()))
        set_uniform_safe("u_light_count", int(len(torch_lights)))

        moon_light = self._moon_world_light()
        if moon_light is None:
            set_uniform_safe("u_moon_light_enabled", 0)
            self.profile_moon_light_enabled = False
            self.profile_moon_light_radius = 0.0
            self.profile_moon_light_strength = 0.0
        else:
            moon_world_x, moon_world_y, moon_radius, moon_strength = moon_light
            set_uniform_safe("u_moon_light_enabled", 1)
            set_uniform_safe("u_moon_light_position", (moon_world_x, moon_world_y))
            set_uniform_safe("u_moon_light_radius", moon_radius)
            set_uniform_safe("u_moon_light_strength", moon_strength)
            set_uniform_safe("u_moon_light_color", (0.82, 0.88, 1.0))
            self.profile_moon_light_enabled = True
            self.profile_moon_light_world_pos = (moon_world_x, moon_world_y)
            self.profile_moon_light_radius = moon_radius
            self.profile_moon_light_strength = moon_strength

        array_positions_set = set_uniform_safe("u_light_positions", tuple(light_positions_flat))
        array_radii_set = set_uniform_safe("u_light_radii", tuple(light_radii))
        if not (array_positions_set and array_radii_set):
            for i in range(MAX_SHADER_TORCH_LIGHTS):
                set_uniform_safe(
                    f"u_light_positions[{i}]",
                    (light_positions_flat[i * 2], light_positions_flat[i * 2 + 1]),
                )
                set_uniform_safe(f"u_light_radii[{i}]", light_radii[i])

        prev_blend_func = self.window.ctx.blend_func
        t0 = time.perf_counter()

        def bind_surface_texture() -> None:
            """Bindet die Surface-Texture kompatibel mit unterschiedlichen Arcade-Versionen."""
            try:
                self._surface_height_texture.use(location=0)
                return
            except TypeError:
                pass

            try:
                self._surface_height_texture.use(0)
                return
            except TypeError:
                pass

            self._surface_height_texture.use()

        try:
            with self.window.ctx.enabled(self.window.ctx.BLEND):
                self.window.ctx.blend_func = (self.window.ctx.DST_COLOR, self.window.ctx.ZERO)
                bind_surface_texture()
                self.sky_quad.render(self.cave_depth_shader_program)
        finally:
            self.window.ctx.blend_func = prev_blend_func

        self.profile_shader_overlay_ms = (time.perf_counter() - t0) * 1000.0

    def _celestial_screen_position(self, progress: float) -> tuple[float, float]:
        """Bildschirmposition auf der stationären Himmelsellipse."""
        p = max(0.0, min(1.0, progress))
        theta = math.pi * p
        center_x = self.window.width * 0.5
        center_y = self.window.height * 0.30
        radius_x = self.window.width * 0.62
        radius_y = self.window.height * 0.69
        x = center_x + radius_x * math.cos(theta)
        y = center_y + radius_y * math.sin(theta)
        return x, y

    def _moon_progress(self) -> float | None:
        """Liefert den normierten Verlauf der Mondbahn oder None, wenn nicht sichtbar."""
        if self.window.time_of_day >= 0.75:
            return (self.window.time_of_day - 0.75) / 0.5
        if self.window.time_of_day < 0.25:
            return (self.window.time_of_day + 0.25) / 0.5
        return None

    def _moon_screen_position(self) -> tuple[float, float] | None:
        """Aktuelle Mondposition im Bildschirmraum."""
        moon_progress = self._moon_progress()
        if moon_progress is None:
            return None
        return self._celestial_screen_position(moon_progress)

    def _moon_world_light(self) -> tuple[float, float, float, float] | None:
        """Weltkoordinaten und Parameter einer mondfarbenen Lichtquelle."""
        moon_screen_pos = self._moon_screen_position()
        if moon_screen_pos is None:
            return None

        sea_level_world_y = (SEA_LEVEL + 1.0) * TILE_SIZE
        if self.window.camera.position[1] < sea_level_world_y - CELESTIAL_HIDE_BELOW_SEA_TILES * TILE_SIZE:
            return None

        moon_x_screen, moon_y_screen = moon_screen_pos
        # Explizites Mapping Screen -> World (gleiche Formel wie _screen_to_world im GameWindow).
        moon_world_x = self.window.camera.position[0] + (moon_x_screen - self.window.width * 0.5)
        moon_world_y = self.window.camera.position[1] + (moon_y_screen - self.window.height * 0.5)

        night_strength = max(0.0, 1.0 - self.day_factor())
        moon_radius = 760.0
        moon_strength = 0.34 + 0.36 * night_strength
        return float(moon_world_x), float(moon_world_y), moon_radius, moon_strength

    def _collect_shader_torch_lights(self, max_lights: int) -> list[tuple[float, float, float]]:
        """Sammelt nahe, sichtbare Torch-Lichter fuer den GPU-Shader in Weltkoordinaten."""
        lights: list[tuple[float, float, float, float]] = []

        min_tile_x, max_tile_x = self.window._get_visible_tile_x_range(margin_tiles=10)
        min_tile_y, max_tile_y = self.window._get_visible_tile_range(margin_tiles=8)
        player_x = float(self.window.player.center_x)
        player_y = float(self.window.player.center_y)

        for (tile_x, tile_y), item_id in self.window.world.placed_items.items():
            if item_id != TORCH:
                continue
            if tile_x < min_tile_x or tile_x > max_tile_x:
                continue
            if tile_y < min_tile_y or tile_y > max_tile_y:
                continue

            light_x = (tile_x + 0.5) * TILE_SIZE
            light_y = (tile_y + 1.0) * TILE_SIZE
            torch_scale = self.torch_daylight_multiplier(light_x, light_y)
            if torch_scale <= 0.01:
                continue
            radius = SHADER_TORCH_RADIUS * torch_scale
            dist_sq = (light_x - player_x) ** 2 + (light_y - player_y) ** 2
            lights.append((dist_sq, light_x, light_y, radius))

        if self.window._is_torch_equipped():
            player_light_pos = self.window.player.get_equipped_light_source_position()
            if player_light_pos is not None:
                light_x = float(player_light_pos[0])
                light_y = float(player_light_pos[1])
                torch_scale = self.torch_daylight_multiplier(light_x, light_y)
                if torch_scale > 0.01:
                    radius = SHADER_TORCH_RADIUS * torch_scale
                    dist_sq = (light_x - player_x) ** 2 + (light_y - player_y) ** 2
                    lights.append((dist_sq, light_x, light_y, radius))

        lights.sort(key=lambda entry: entry[0])
        return [(x, y, r) for _dist, x, y, r in lights[:max_lights]]

    def draw_underground_darkness_overlay(self):
        """Standardpfad: Shader-Overlay; CPU-Pfad bleibt optional per Debug-Flag."""
        if self.use_cpu_underground_overlay_debug:
            t0 = time.perf_counter()
            self._draw_underground_darkness_overlay_cpu()
            self.profile_cpu_overlay_ms = (time.perf_counter() - t0) * 1000.0
            self.profile_shader_overlay_ms = 0.0
            return

        self.profile_cpu_overlay_ms = 0.0
        self._draw_underground_darkness_overlay_shader()

    def profile_debug_line(self) -> str:
        """Kurzformat fuer HUD-Debugwerte rund um Underground-Lighting."""
        mode = "CPU" if self.use_cpu_underground_overlay_debug else "GPU"
        moon_state = "on" if self.profile_moon_light_enabled else "off"
        return (
            f"Light[{mode}] cpu={self.profile_cpu_overlay_ms:5.2f}ms "
            f"surf={self.profile_surface_map_update_ms:5.2f}ms "
            f"shader={self.profile_shader_overlay_ms:5.2f}ms "
            f"moon={moon_state} r={self.profile_moon_light_radius:4.0f} s={self.profile_moon_light_strength:0.2f}"
        )

    @staticmethod
    def draw_glow_orb(
        x: float,
        y: float,
        core_radius: float,
        glow_color: tuple[int, int, int],
        strength: float,
    ):
        """Zeichnet einen günstigen Pseudo-Bloom über mehrere weiche Ringe."""
        ring_count = 5
        for i in range(ring_count, 0, -1):
            t = i / ring_count
            radius = core_radius + (24.0 * strength) * (1.0 + t * 2.0)
            alpha = int(46 * strength * (t**1.5))
            if alpha <= 0:
                continue
            arcade.draw_circle_filled(x, y, radius, (glow_color[0], glow_color[1], glow_color[2], alpha))

    def draw_celestials(self):
        """Zeichnet Sonne und Mond von rechts nach links über den Himmel."""
        if self.sky_background_blend() > 0.65:
            return

        sea_level_world_y = (SEA_LEVEL + 1.0) * TILE_SIZE
        if self.window.camera.position[1] < sea_level_world_y - CELESTIAL_HIDE_BELOW_SEA_TILES * TILE_SIZE:
            return

        sun_progress = (self.window.time_of_day - 0.25) / 0.5
        if 0.0 <= sun_progress <= 1.0:
            sun_x, sun_y = self._celestial_screen_position(sun_progress)
            if self.sun_sprite is not None:
                self.sun_sprite.center_x = sun_x
                self.sun_sprite.center_y = sun_y
                self.sun_sprite.color = (255, 255, 255)
                self.sun_sprite.alpha = 255
                arcade.draw_sprite(self.sun_sprite)
            else:
                arcade.draw_circle_filled(sun_x, sun_y, 34, (255, 236, 130, 255))

    def draw_moon_no_ambient(self):
        """Zeichnet den Mond mit Originaltextur in einem separaten Pass ohne Ambient-Tint."""
        if self.sky_background_blend() > 0.65:
            return

        sea_level_world_y = (SEA_LEVEL + 1.0) * TILE_SIZE
        if self.window.camera.position[1] < sea_level_world_y - CELESTIAL_HIDE_BELOW_SEA_TILES * TILE_SIZE:
            return

        moon_screen_pos = self._moon_screen_position()
        if moon_screen_pos is None:
            return

        moon_x, moon_y = moon_screen_pos
        if self.moon_sprite is not None:
            self.moon_sprite.center_x = moon_x
            self.moon_sprite.center_y = moon_y
            self.moon_sprite.color = (255, 255, 255)
            self.moon_sprite.alpha = 255
            arcade.draw_sprite(self.moon_sprite)
        else:
            arcade.draw_circle_filled(moon_x, moon_y, 26, (245, 248, 255, 255))

    def draw_stars_no_ambient(self):
        """Zeichnet kleine Sterne ohne globales Ambient; lokale Lichter dimmen Sterne."""
        if self.sky_background_blend() > 0.58:
            return

        night_strength = max(0.0, 1.0 - self.day_factor())
        if night_strength <= 0.18:
            return

        # Sterne werden nur nachts sichtbar, aber nicht vom globalen Ambient beeinflusst.
        night_alpha_scale = min(1.0, max(0.0, (night_strength - 0.18) / 0.62))

        def smoothstep_py(edge0: float, edge1: float, x: float) -> float:
            if edge1 <= edge0:
                return 1.0 if x >= edge1 else 0.0
            t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
            return t * t * (3.0 - 2.0 * t)

        camera_x, camera_y = self.window.camera.position
        half_w = self.window.width * 0.5
        half_h = self.window.height * 0.5
        torch_lights = self._collect_shader_torch_lights(MAX_SHADER_TORCH_LIGHTS)
        moon_light = self._moon_world_light()
        ambient_color = self.ambient_color()
        ambient_luma = max(0.05, (ambient_color[0] + ambient_color[1] + ambient_color[2]) / (3.0 * 255.0))
        ambient_compensation = min(3.0, 1.0 / ambient_luma)

        for sx, sy, size, phase in self._star_field:
            # X-Parallaxe: langsamer Drift relativ zur Kamera-X.
            # Die Sternkarte wiederholt sich erst nach zwei Bildschirmbreiten.
            repeat_width = self.window.width * 2.0
            x = (sx * repeat_width - camera_x * 0.018) % repeat_width
            if x > self.window.width:
                continue
            y = sy * self.window.height
            star_brightness = 0.72 + 0.28 * math.sin(phase)
            base_alpha = (120 + 95 * star_brightness) * night_alpha_scale

            world_x = camera_x + (x - half_w)
            world_y = camera_y + (y - half_h)
            local_dim = 0.0

            for light_x, light_y, radius in torch_lights:
                r = max(1.0, radius)
                dist = math.hypot(world_x - light_x, world_y - light_y)
                falloff = 1.0 - smoothstep_py(r * 0.10, r, dist)
                local_dim += falloff * 0.92

            if moon_light is not None:
                moon_x, moon_y, moon_radius, moon_strength = moon_light
                moon_dist = math.hypot(world_x - moon_x, world_y - moon_y)
                moon_falloff = 1.0 - smoothstep_py(moon_radius * 0.04, moon_radius, moon_dist)
                local_dim += moon_falloff * moon_strength

            local_dim = max(0.0, min(0.95, local_dim))
            alpha = int(base_alpha * (1.0 - local_dim) * ambient_compensation)
            alpha = max(0, min(255, alpha))
            if alpha <= 8:
                continue

            radius = size
            arcade.draw_circle_filled(x, y, radius, (238, 244, 255, alpha))
