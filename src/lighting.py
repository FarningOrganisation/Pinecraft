"""Lighting and sky rendering helpers for the game."""

import math

import arcade
from arcade.future.light import Light
from arcade.gl import geometry as gl_geometry

from blocks import AIR, get_block_light_opacity, is_block_skylight_surface
from paths import textures_dir
from settings import TILE_SIZE, WORLD_HEIGHT
from world_generation import SEA_LEVEL

CELESTIAL_HIDE_BELOW_SEA_TILES = 10


class LightingSystem:
    """Encapsulates sky, daylight, cave darkness and torch lighting logic."""

    def __init__(self, window):
        self.window = window
        self.torch_light_color = (255, 190, 100)

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

                    fragColor = vec4(color, 1.0);
                }
            """,
        )
        self.sky_quad = gl_geometry.quad_2d_fs()

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

    def sky_background_blend(self) -> float:
        """0 = normale Sky-Farbe, 1 = tiefe Höhle; Abstand zur nächsten Open-Air-Säule bestimmt den Übergang."""
        player_tile_x = int(self.window.player.center_x // TILE_SIZE)
        player_tile_y = int(self.window.player.center_y // TILE_SIZE)
        search_radius = 12
        nearest_sky_distance = float("inf")

        for ox in range(-search_radius, search_radius + 1):
            for oy in range(-search_radius, search_radius + 1):
                tile_x = player_tile_x + ox
                tile_y = player_tile_y + oy
                if tile_y < 0 or tile_y >= WORLD_HEIGHT:
                    continue
                if self.window.world.get_block(tile_x, tile_y, generate_if_missing=False) != AIR:
                    continue
                if not self.is_sky_lit_air(tile_x, tile_y, max_scan=18):
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
        if day_factor >= 0.46:
            return (255, 255, 255)
        if day_factor > 0.22:
            t = (day_factor - 0.22) / (0.46 - 0.22)
            return self.lerp_color((42, 50, 74), (255, 255, 255), t)
        return (28, 34, 52)

    def draw_sky_shader(self):
        """Zeichnet den dynamischen Himmel per Fullscreen-Fragment-Shader."""
        self.sky_shader_program["u_day_factor"] = float(self.day_factor())
        self.sky_shader_program["u_time_of_day"] = float(self.window.time_of_day)
        self.sky_shader_program["u_underground"] = float(self.sky_background_blend())
        self.sky_quad.render(self.sky_shader_program)

    def _is_torch_equipped(self) -> bool:
        """True, wenn der aktuell ausgewählte Hotbar-Slot eine Fackel enthält."""
        return self.window._is_torch_equipped()

    def torch_daylight_multiplier(self, world_x: float, world_y: float) -> float:
        """Torch visibility fades almost to zero in bright daylight and rises again toward dusk/night."""
        day_factor = self.day_factor()
        if day_factor >= 0.72:
            return 0.0
        if day_factor <= 0.15:
            return 1.0
        return max(0.0, 1.0 - ((day_factor - 0.15) / (0.72 - 0.15)) * 0.98)

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

        for tile_x in range(min_tile_x, max_tile_x + 1):
            for tile_y in range(min_tile_y, max_tile_y + 1):
                if self.window.world.get_block(tile_x, tile_y, generate_if_missing=False) != AIR:
                    continue

                sky_clear = True
                for check_y in range(tile_y + 1, min(max_tile_y + 8, WORLD_HEIGHT)):
                    if self.window.world.get_block(tile_x, check_y, generate_if_missing=False) != AIR:
                        sky_clear = False
                        break

                if sky_clear:
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

    def draw_underground_darkness_overlay(self):
        """Zeichnet die Tiefe anhand der Nachbar-Block-Struktur; keine globale Höhlen-Erkennung mehr."""
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

    @staticmethod
    def draw_glow_orb(
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

    def draw_celestials(self):
        """Zeichnet Sonne und Mond von rechts nach links über den Himmel."""
        if self.sky_background_blend() > 0.65:
            return

        sea_level_world_y = (SEA_LEVEL + 1.0) * TILE_SIZE
        if self.window.camera.position[1] < sea_level_world_y - CELESTIAL_HIDE_BELOW_SEA_TILES * TILE_SIZE:
            return

        sea_level_screen_y = sea_level_world_y - self.window.camera.position[1] + self.window.height / 2
        if sea_level_screen_y < -0.25 * self.window.height or sea_level_screen_y > 1.25 * self.window.height:
            return

        def celestial_position(progress: float) -> tuple[float, float]:
            p = max(0.0, min(1.0, progress))
            theta = math.pi * p
            center_x = self.window.width * 0.5
            center_y = sea_level_screen_y
            radius_x = self.window.width * 0.62
            radius_y = self.window.height * 0.64
            x = center_x + radius_x * math.cos(theta)
            y = center_y + radius_y * math.sin(theta)
            return x, y

        sun_progress = (self.window.time_of_day - 0.25) / 0.5
        if 0.0 <= sun_progress <= 1.0:
            sun_x, sun_y = celestial_position(sun_progress)
            if self.sun_sprite is not None:
                self.sun_sprite.center_x = sun_x
                self.sun_sprite.center_y = sun_y
                self.sun_sprite.color = (255, 255, 255)
                self.sun_sprite.alpha = 255
                arcade.draw_sprite(self.sun_sprite)
            else:
                arcade.draw_circle_filled(sun_x, sun_y, 34, (255, 236, 130, 255))

        moon_progress: float | None = None
        if self.window.time_of_day >= 0.75:
            moon_progress = (self.window.time_of_day - 0.75) / 0.5
        elif self.window.time_of_day < 0.25:
            moon_progress = (self.window.time_of_day + 0.25) / 0.5

        if moon_progress is not None:
            moon_x, moon_y = celestial_position(moon_progress)
            self.draw_glow_orb(moon_x, moon_y, 26, (170, 208, 255), strength=0.78)
            if self.moon_sprite is not None:
                self.moon_sprite.center_x = moon_x
                self.moon_sprite.center_y = moon_y
                self.moon_sprite.alpha = 255
                arcade.draw_sprite(self.moon_sprite)
            else:
                arcade.draw_circle_filled(moon_x, moon_y, 26, (214, 226, 255, 235))
                arcade.draw_circle_filled(moon_x + 7, moon_y + 2, 19, (12, 20, 42, 220))
