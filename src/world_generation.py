"""Deterministische Terrain-Generierung für Pinecraft.

Dieses Modul enthält nur die prozedurale Erzeugung der Welt.
Die Welt-Daten selbst liegen in world.py.
"""

from __future__ import annotations

import math
from pathlib import Path

import arcade

from blocks import (
    AIR,
    BEDROCK,
    BLOCK_TEXTURES,
    COAL_ORE,
    DIAMOND_ORE,
    GOLD_ORE,
    IRON_ORE,
    LEAVES,
    OAK,
    SAND,
    STONE,
    is_block_falling,
    is_block_water_passable,
)
from resource_manager import resource_manager
from sand import local_fall_depth as sand_local_fall_depth
from sand import slide_decision_signature as sand_slide_decision_signature
from sand import slide_probability as sand_slide_probability
from settings import CHUNK_WIDTH, TILE_SIZE, WORLD_HEIGHT
from tree import build_oak_tree_layout, oak_trunk_height
from world import Chunk, World, world_to_chunk_and_local
from world_gen_config import (
    DEFAULT_WORLD_GEN_CONFIG,
    BiomeDefinition,
    WorldGenConfig,
    get_biome_by_name,
    normalized_biome_probabilities,
    validate_world_gen_config,
)

WATER_TEXTURE = resource_manager.load_texture_in_textures(Path("blocks") / "water.png")
WATER_VISUAL_STEPS = 8
WATER_RENDER_THRESHOLD = 0.02
LAVA_TEXTURE = resource_manager.load_texture_in_textures(Path("blocks") / "lava.png")
LAVA_VISUAL_STEPS = 8
LAVA_RENDER_THRESHOLD = 0.02

# Default-Config bleibt als Modulkonstanten sichtbar, damit existierende
# Aufrufer/Tests weiter funktionieren.
WORLD_GEN_CONFIG = DEFAULT_WORLD_GEN_CONFIG
SEA_LEVEL = WORLD_GEN_CONFIG.sea_level
UNDERGROUND_WATER_MAX_Y = WORLD_GEN_CONFIG.underground_water_max_y
UNDERGROUND_WATER_PREFERRED_Y = WORLD_GEN_CONFIG.underground_water_preferred_y
UNDERGROUND_WATER_PREFERRED_HALF_SPAN = WORLD_GEN_CONFIG.underground_water_preferred_half_span
UNDERGROUND_LAVA_MAX_Y = WORLD_GEN_CONFIG.underground_lava_max_y
UNDERGROUND_LAVA_MIN_Y = WORLD_GEN_CONFIG.underground_lava_min_y
COASTAL_BEACH_BAND = WORLD_GEN_CONFIG.coastal_beach_band

# Profile-Format: (terrain_amp, detail_amp, tree_density, rockiness)
_PLAINS_BIOME = get_biome_by_name(WORLD_GEN_CONFIG, "plains")
_MIXED_BIOME = get_biome_by_name(WORLD_GEN_CONFIG, "mixed")
_ROCKY_BIOME = get_biome_by_name(WORLD_GEN_CONFIG, "rocky")
_MOUNTAIN_BIOME = get_biome_by_name(WORLD_GEN_CONFIG, "mountain")
BIOME_PROFILE_PLAINS = (_PLAINS_BIOME.profile.as_tuple() if _PLAINS_BIOME else (0.62, 0.45, 1.15, 0.15))
BIOME_PROFILE_MIXED = (_MIXED_BIOME.profile.as_tuple() if _MIXED_BIOME else (0.82, 0.55, 0.90, 0.45))
BIOME_PROFILE_ROCKY = (_ROCKY_BIOME.profile.as_tuple() if _ROCKY_BIOME else (1.0, 0.65, 0.58, 1.0))
BIOME_PROFILE_MOUNTAIN = (_MOUNTAIN_BIOME.profile.as_tuple() if _MOUNTAIN_BIOME else (1.35, 0.72, 0.42, 1.15))


class WorldGenerator:
    """Erzeugt deterministisches Terrain für einen World-Container."""

    def __init__(self, seed: int = 1337, config: WorldGenConfig | None = None):
        self.seed = seed
        self.config = config or DEFAULT_WORLD_GEN_CONFIG
        for hint in validate_world_gen_config(self.config):
            print(f"[worldgen][hint] {hint}")
        self._biome_probability_table = self._build_biome_probability_table(self.config.biomes)
        self._land_biome_probability_table = self._build_biome_probability_table(
            tuple(biome for biome in self.config.biomes if not biome.is_ocean)
        )
        self._ocean_biome_probability_table = self._build_biome_probability_table(
            tuple(biome for biome in self.config.biomes if biome.is_ocean)
        )
        self._biome_cache: dict[int, BiomeDefinition] = {}
        self._terrain_height_cache: dict[int, int] = {}
        self._ocean_zone_cell_cache: dict[int, tuple[bool, float]] = {}
        self._ocean_island_cell_cache: dict[int, tuple[bool, int, int, int]] = {}
        probabilities = normalized_biome_probabilities(self.config)
        self._ocean_target_probability = sum(probability for biome, probability in probabilities if biome.is_ocean)

    def _build_biome_probability_table(self, biomes: tuple[BiomeDefinition, ...]) -> list[tuple[float, BiomeDefinition]]:
        """Erzeugt kumulative Wahrscheinlichkeiten aus Biome-Gewichten."""
        positive = [(biome, float(biome.weight)) for biome in biomes if float(biome.weight) > 0.0]
        if not positive:
            if biomes:
                fallback = biomes[0]
                return [(1.0, fallback)]
            return []

        total_weight = sum(weight for _biome, weight in positive)
        if total_weight <= 0.0:
            fallback = positive[0][0]
            return [(1.0, fallback)]

        table: list[tuple[float, BiomeDefinition]] = []
        cumulative = 0.0
        for biome, weight in positive:
            probability = weight / total_weight
            cumulative += probability
            table.append((cumulative, biome))

        if table:
            table[-1] = (1.0, table[-1][1])
        return table

    def _pick_biome_from_table(self, selector: float, table: list[tuple[float, BiomeDefinition]]) -> BiomeDefinition:
        """Wählt ein Biome aus einer kumulativen Wahrscheinlichkeits-Tabelle."""
        if not table:
            if self.config.biomes:
                return self.config.biomes[0]
            return BiomeDefinition(name="fallback", weight=1.0, profile=DEFAULT_WORLD_GEN_CONFIG.biomes[0].profile)

        for cumulative_probability, biome in table:
            if selector <= cumulative_probability:
                return biome
        return table[-1][1]

    def _hash_u32(self, value: int) -> int:
        """Kleiner deterministischer 32-bit Hash für stabile Zufallswerte."""
        value = (value ^ 61) ^ (value >> 16)
        value = (value + (value << 3)) & 0xFFFFFFFF
        value = value ^ (value >> 4)
        value = (value * 0x27D4EB2D) & 0xFFFFFFFF
        value = value ^ (value >> 15)
        return value & 0xFFFFFFFF

    def _rand01(self, world_x: int, salt: int) -> float:
        """Deterministischer Zufallswert im Bereich [0, 1)."""
        mixed = (world_x * 374761393 + self.seed * 668265263 + salt * 1442695040888963407) & 0xFFFFFFFF
        return self._hash_u32(mixed) / 4294967296.0

    def _rand01_2d(self, world_x: int, world_y: int, salt: int) -> float:
        """Deterministischer Zufallswert für 2D-Koordinaten im Bereich [0, 1)."""
        mixed = (
            world_x * 374761393
            + world_y * 668265263
            + self.seed * 2246822519
            + salt * 3266489917
        ) & 0xFFFFFFFF
        return self._hash_u32(mixed) / 4294967296.0

    @staticmethod
    def _smoothstep01(value: float) -> float:
        """Glättet einen Wert aus [0, 1] für weichere Noise-Übergänge."""
        v = max(0.0, min(1.0, value))
        return v * v * (3.0 - 2.0 * v)

    @staticmethod
    def _lerp(a: float, b: float, t: float) -> float:
        """Lineare Interpolation zwischen zwei Werten."""
        return a + (b - a) * t

    def _value_noise_2d(self, world_x: int, world_y: int, cell_size: int, salt: int) -> float:
        """Deterministisches 2D-Value-Noise in [0, 1] auf Weltkoordinaten."""
        if cell_size <= 1:
            return self._rand01_2d(world_x, world_y, salt=salt)

        gx0 = math.floor(world_x / cell_size)
        gy0 = math.floor(world_y / cell_size)
        gx1 = gx0 + 1
        gy1 = gy0 + 1

        tx = (world_x - gx0 * cell_size) / cell_size
        ty = (world_y - gy0 * cell_size) / cell_size
        sx = self._smoothstep01(tx)
        sy = self._smoothstep01(ty)

        n00 = self._rand01_2d(gx0, gy0, salt=salt)
        n10 = self._rand01_2d(gx1, gy0, salt=salt)
        n01 = self._rand01_2d(gx0, gy1, salt=salt)
        n11 = self._rand01_2d(gx1, gy1, salt=salt)

        ix0 = self._lerp(n00, n10, sx)
        ix1 = self._lerp(n01, n11, sx)
        return self._lerp(ix0, ix1, sy)

    def _is_ocean_zone(self, world_x: int) -> bool:
        """Makro-Zone fuer Ozeane, damit Ocean-Biome gebuendelt statt haeufig gestreut erscheinen."""
        if not self._ocean_biome_probability_table:
            return False

        cfg = self.config

        if cfg.single_ocean_mode:
            configured_width = int(cfg.single_ocean_width)
            width = configured_width if configured_width > 0 else int(cfg.biome_noise_cell_size)
            width = max(8, width)
            half_width = width / 2.0
            return abs(float(world_x - int(cfg.single_ocean_center_x))) <= half_width

        cell_size = max(64, int(cfg.ocean_zone_cell_size))
        cell_index = math.floor(world_x / cell_size)

        cached = self._ocean_zone_cell_cache.get(cell_index)
        if cached is None:
            if cfg.ocean_zone_threshold >= 0.0:
                threshold = float(cfg.ocean_zone_threshold)
            else:
                ocean_probability = max(0.06, min(0.45, float(self._ocean_target_probability) * 1.10))
                threshold = 1.0 - ocean_probability

            center_score = self._rand01_2d(cell_index, self.seed * 3 + 17, salt=1691)
            left_score = self._rand01_2d(cell_index - 1, self.seed * 3 + 17, salt=1691)
            right_score = self._rand01_2d(cell_index + 1, self.seed * 3 + 17, salt=1691)

            left_candidate = left_score >= threshold
            right_candidate = right_score >= threshold
            is_candidate = center_score >= threshold
            if is_candidate and left_candidate and center_score <= left_score:
                is_candidate = False
            if is_candidate and right_candidate and center_score < right_score:
                is_candidate = False

            width_noise = self._rand01_2d(cell_index, self.seed * 5 + 29, salt=1693)
            half_width = 0.23 + 0.16 * width_noise
            cached = (is_candidate, half_width)

            if len(self._ocean_zone_cell_cache) >= 8192:
                self._ocean_zone_cell_cache.clear()
            self._ocean_zone_cell_cache[cell_index] = cached

        is_active_cell, half_width = cached
        if not is_active_cell:
            return False

        in_cell = (world_x - cell_index * cell_size) / float(cell_size)
        center_distance = abs(in_cell - 0.5)
        if center_distance <= half_width:
            return True

        fringe = half_width + 0.04
        if center_distance > fringe:
            return False

        shoreline_noise = self._value_noise_2d(world_x, self.seed * 7 + 41, cell_size=max(20, cell_size // 10), salt=1697)
        return shoreline_noise > 0.58

    def _ocean_island_cell_profile(self, cell_index: int, cell_size: int) -> tuple[bool, int, int, int]:
        """Erzeugt deterministische Insel-Parameter pro Ocean-Cell."""
        cached = self._ocean_island_cell_cache.get(cell_index)
        if cached is not None:
            return cached

        cfg = self.config
        threshold = max(0.0, min(1.0, float(cfg.ocean_island_threshold)))
        active_roll = self._rand01_2d(cell_index, self.seed * 11 + 7, salt=1741)
        active = active_roll >= threshold
        if not active:
            profile = (False, 0, 0, 0)
        else:
            center_offset_roll = self._rand01_2d(cell_index, self.seed * 13 + 11, salt=1743)
            center_offset = int((center_offset_roll - 0.5) * (cell_size * 0.62))
            center_x = cell_index * cell_size + (cell_size // 2) + center_offset

            min_radius = max(1, int(cfg.ocean_island_min_radius))
            max_radius = max(min_radius, int(cfg.ocean_island_max_radius))
            radius_span = max_radius - min_radius + 1
            radius_roll = self._rand01_2d(cell_index, self.seed * 17 + 19, salt=1745)
            radius = min_radius + int(radius_roll * radius_span)
            radius = max(min_radius, min(max_radius, radius))

            min_peak = max(1, int(cfg.ocean_island_min_peak_above_sea))
            max_peak = max(min_peak, int(cfg.ocean_island_max_peak_above_sea))
            peak_span = max_peak - min_peak + 1
            peak_roll = self._rand01_2d(cell_index, self.seed * 19 + 23, salt=1747)
            peak_height = min_peak + int(peak_roll * peak_span)
            peak_height = max(min_peak, min(max_peak, peak_height))

            profile = (True, center_x, radius, peak_height)

        if len(self._ocean_island_cell_cache) >= 8192:
            self._ocean_island_cell_cache.clear()
        self._ocean_island_cell_cache[cell_index] = profile
        return profile

    def _ocean_island_surface_override(self, world_x: int, base_surface_y: int, is_ocean_column: bool) -> int:
        """Hebt in Ocean-Spalten kleine Inseln ueber Meeresspiegel an."""
        cfg = self.config
        if not is_ocean_column or not cfg.ocean_islands_enabled:
            return base_surface_y

        cell_size = max(24, int(cfg.ocean_island_cell_size))
        cell_index = math.floor(world_x / cell_size)
        best_top_y = base_surface_y

        for island_cell in (cell_index - 1, cell_index, cell_index + 1):
            active, center_x, radius, peak_height = self._ocean_island_cell_profile(island_cell, cell_size)
            if not active or radius <= 0:
                continue

            dist = abs(world_x - center_x)
            if dist > radius:
                continue

            t = 1.0 - (dist / float(max(1, radius)))
            local_peak = cfg.sea_level + int(max(1.0, peak_height * (t * t)))
            if local_peak > best_top_y:
                best_top_y = local_peak

        return max(base_surface_y, min(WORLD_HEIGHT - 2, int(best_top_y)))

    def _biome_for_world_x(self, world_x: int) -> BiomeDefinition:
        """Waehlt ein Biome ueber normalisierte Gewichte und glattes Noise."""
        cached = self._biome_cache.get(world_x)
        if cached is not None:
            return cached

        cell_size = max(8, int(self.config.biome_noise_cell_size))
        if self._is_ocean_zone(world_x) and self._ocean_biome_probability_table:
            selector = self._value_noise_2d(world_x, self.seed + 91, cell_size=max(32, cell_size), salt=1711)
            biome = self._pick_biome_from_table(selector, self._ocean_biome_probability_table)
        else:
            selector = self._value_noise_2d(world_x, self.seed, cell_size=cell_size, salt=1669)
            table = self._land_biome_probability_table or self._biome_probability_table
            biome = self._pick_biome_from_table(selector, table)

        if len(self._biome_cache) >= 32768:
            self._biome_cache.clear()
        self._biome_cache[world_x] = biome
        return biome

    def _is_cave_air(self, world_x: int, y: int, surface_y: int, biome_cave_density_multiplier: float = 1.0) -> bool:
        """Entscheidet deterministisch, ob ein Untergrund-Block als Höhle leer bleibt."""
        cfg = self.config
        if y <= 2:
            return False

        depth = surface_y - y
        if depth < cfg.cave_min_depth:
            return False

        depth_span = max(1.0, float(cfg.cave_depth_span))
        depth_factor = min(1.0, max(0.0, (depth - cfg.cave_min_depth) / depth_span))

        # Zwei Skalen erzeugen verbundene Tunnel plus größere Kammern.
        large = self._value_noise_2d(world_x, y, cell_size=18, salt=811)
        medium = self._value_noise_2d(world_x, y, cell_size=9, salt=823)
        chamber = self._value_noise_2d(world_x, y, cell_size=30, salt=839)

        # Ridges statt Blobs: Nähe zur Mittellinie erzeugt gangartige Strukturen.
        ridge_large = abs(large - 0.5) * 2.0
        ridge_medium = abs(medium - 0.5) * 2.0
        tunnel_signal = ridge_large * 0.68 + ridge_medium * 0.32

        cave_density = max(0.01, float(cfg.cave_density_multiplier)) * max(0.01, float(biome_cave_density_multiplier))
        tunnel_threshold = (cfg.cave_tunnel_base_threshold + cfg.cave_tunnel_depth_bonus * depth_factor) * cave_density
        chamber_open = chamber > (cfg.cave_chamber_base_threshold - cfg.cave_chamber_depth_bonus * depth_factor) and tunnel_signal < (
            (cfg.cave_chamber_signal_base + cfg.cave_chamber_signal_depth_bonus * depth_factor) * cave_density
        )
        return tunnel_signal < tunnel_threshold or chamber_open

    def _pick_underground_block(
        self,
        world_x: int,
        y: int,
        surface_y: int,
        *,
        base_block_id: int = STONE,
        biome_ore_density_multiplier: float = 1.0,
    ) -> int:
        """Wählt für tiefe Steinbereiche deterministisch passende Erze aus."""
        cfg = self.config
        depth_from_surface = max(0, surface_y - y)
        if depth_from_surface < 4:
            return base_block_id

        # Mehr Erze in größerer Tiefe.
        ore_depth_span = max(1.0, float(cfg.ore_depth_span))
        depth_factor = min(1.0, max(0.0, (depth_from_surface - 4) / ore_depth_span))
        ore_density = max(0.01, float(cfg.ore_density_multiplier)) * max(0.01, float(biome_ore_density_multiplier))

        # Grobe 2D-Patches (vein-artig), ohne teuren Noise-Overhead.
        patch_x = world_x // 4
        patch_y = y // 3
        richness = 0.7 + 0.7 * self._rand01_2d(patch_x, patch_y, salt=719)

        # Insgesamt weniger Erze; Kohle und Eisen in aehnlicher Hauefigkeit.
        coal_chance = (cfg.coal_base_chance + cfg.coal_depth_bonus * depth_factor) * richness * ore_density
        iron_chance = (cfg.iron_base_chance + cfg.iron_depth_bonus * depth_factor) * richness * ore_density

        very_deep_limit = int(WORLD_HEIGHT * cfg.gold_max_y_ratio)
        ultra_deep_limit = int(WORLD_HEIGHT * cfg.diamond_max_y_ratio)
        gold_chance = 0.0
        diamond_chance = 0.0
        if y <= very_deep_limit:
            gold_chance = (cfg.gold_base_chance + cfg.gold_depth_bonus * depth_factor) * richness * ore_density
        if y <= ultra_deep_limit:
            diamond_chance = (cfg.diamond_base_chance + cfg.diamond_depth_bonus * depth_factor) * richness * ore_density

        # Separate deterministische Rolls pro Erztyp verhindern Ueberlagerung.
        diamond_roll = self._rand01_2d(world_x, y, salt=701)
        gold_roll = self._rand01_2d(world_x, y, salt=703)
        iron_roll = self._rand01_2d(world_x, y, salt=705)
        coal_roll = self._rand01_2d(world_x, y, salt=707)

        # Seltene Erze zuerst prüfen, damit deren Rarität erhalten bleibt.
        if diamond_chance > 0 and diamond_roll < diamond_chance:
            return DIAMOND_ORE
        if gold_chance > 0 and gold_roll < gold_chance:
            return GOLD_ORE
        if iron_roll < iron_chance:
            return IRON_ORE
        if coal_roll < coal_chance:
            return COAL_ORE
        return base_block_id

    def _pick_underground_liquid(self, world_x: int, y: int) -> str | None:
        """Wählt für eine Höhlenzelle deterministisch Wasser oder Lava nach Tiefe."""
        cfg = self.config
        if y <= cfg.underground_lava_min_y:
            return None

        depth_norm = max(0.0, min(1.0, 1.0 - (y / float(max(1, cfg.underground_water_max_y)))))

        # Wasser bevorzugt mittlere Tiefen als glatte Glocke um einen Zielbereich.
        medium_water_factor = 1.0 - abs(y - cfg.underground_water_preferred_y) / float(max(1, cfg.underground_water_preferred_half_span))
        medium_water_factor = max(0.0, min(1.0, medium_water_factor))

        # Lava bevorzugt tiefe Schichten deutlich stärker.
        lava_span = max(1, cfg.underground_lava_max_y - cfg.underground_lava_min_y)
        lava_depth_factor = max(0.0, min(1.0, (cfg.underground_lava_max_y - y) / float(lava_span)))
        lava_depth_factor = lava_depth_factor**1.6

        # In Erz-Tiefen wird Lava zusätzlich begünstigt, damit Mining riskanter wird.
        very_deep_limit = int(WORLD_HEIGHT * cfg.gold_max_y_ratio)
        ultra_deep_limit = int(WORLD_HEIGHT * cfg.diamond_max_y_ratio)
        lava_hazard_bonus = 0.0
        if y <= very_deep_limit:
            lava_hazard_bonus += 0.10
        if y <= ultra_deep_limit:
            lava_hazard_bonus += 0.08

        selector = self._value_noise_2d(world_x, y, cell_size=14, salt=1217)

        lava_threshold = min(0.94, 0.20 + 0.62 * lava_depth_factor + lava_hazard_bonus)
        water_threshold = 0.80 - 0.30 * medium_water_factor - 0.10 * depth_norm
        if y <= very_deep_limit:
            water_threshold += 0.06

        if y <= cfg.underground_lava_max_y and selector < lava_threshold:
            return "lava"
        if y <= cfg.underground_water_max_y and selector > water_threshold:
            return "water"
        return None

    def _biome_profile(self, world_x: int) -> tuple[float, float, float, float]:
        """Gibt (terrain_amp, detail_amp, tree_density, rockiness) zurück."""
        biome = self._biome_for_world_x(world_x)
        return biome.profile.as_tuple()

    def _terrain_height_for_world_x(self, world_x: int, biome: BiomeDefinition | None = None) -> int:
        """Erzeugt den Terrain-Hoehenwert fuer eine Welt-X-Koordinate mit Cache."""
        cached_height = self._terrain_height_cache.get(world_x)
        if cached_height is not None:
            return cached_height

        base_height = WORLD_HEIGHT // 2
        selected_biome = biome or self._biome_for_world_x(world_x)
        terrain_amp, detail_amp, _tree_density, _rockiness = selected_biome.profile.as_tuple()

        large_wave = math.sin((world_x + self.seed) * 0.036) * 9.0 * terrain_amp
        medium_wave = math.cos((world_x + self.seed) * 0.010) * 6.0 * terrain_amp
        small_wave = math.sin((world_x + self.seed) * 0.075) * 1.6 * detail_amp
        detail_wave = math.cos((world_x + self.seed) * 0.15) * 0.8 * detail_amp
        jitter = (self._rand01(world_x, salt=31) - 0.5) * 1.0 * detail_amp

        height = (
            base_height
            + large_wave
            + medium_wave
            + small_wave
            + detail_wave
            + jitter
        )
        height += float(selected_biome.height_bias)

        if not selected_biome.is_ocean:
            height += self._mountain_peak_add(world_x)

        if selected_biome.is_ocean:
            height = min(height, self.config.sea_level - 1)

        clamped_height = max(8, min(WORLD_HEIGHT - 2, int(height)))
        if len(self._terrain_height_cache) >= 65536:
            self._terrain_height_cache.clear()
        self._terrain_height_cache[world_x] = clamped_height
        return clamped_height

    def _mountain_peak_add(self, world_x: int) -> float:
        """Seltene breite Bergzentren fuer deutlich höhere Berge."""
        cell_size = 220
        cell = int(math.floor(world_x / cell_size))
        total = 0.0

        for c in (cell - 1, cell, cell + 1):
            # Nur ein Teil der Zellen bekommt echte Peak-Strukturen.
            if self._rand01(c, salt=613) > 0.34:
                continue

            center_offset = int((self._rand01(c, salt=601) - 0.5) * 120)
            center_x = c * cell_size + center_offset
            width = 44 + int(self._rand01(c, salt=607) * 64)   # 44..108 tiles
            amplitude = 30.0 + self._rand01(c, salt=619) * 78.0  # 30..108 height

            dist = abs(world_x - center_x)
            if dist > width:
                continue

            t = 1.0 - dist / width
            total += amplitude * (t * t)

        return total

    def terrain_height(self, chunk_x: int, local_x: int) -> int:
        """Erzeugt einen stabilen, wiederholbaren Höhenwert mit Sinuswellen."""
        world_x = chunk_x * CHUNK_WIDTH + local_x
        return self._terrain_height_for_world_x(world_x)

    def _has_tree(self, world_x: int, biome: BiomeDefinition | None = None) -> bool:
        """Deterministische Baumverteilung entlang der X-Achse."""
        selected_biome = biome or self._biome_for_world_x(world_x)
        if not selected_biome.allow_trees:
            return False
        _terrain_amp, _detail_amp, tree_density, _rockiness = selected_biome.profile.as_tuple()
        value = (world_x * 73856093 + self.seed * 19349663) & 0xFFFFFFFF
        base_tree = value % 17 == 0
        if not base_tree:
            return False
        return self._rand01(world_x, salt=401) < min(1.0, tree_density)

    def _is_ocean_column(self, world_x: int, surface_y: int, biome: BiomeDefinition | None = None) -> bool:
        """True fuer Ocean-Biome und tiefe Talspalten; kleine Landluecken werden geglaettet."""
        if self._is_ocean_column_base(world_x, surface_y, biome=biome):
            return True

        cfg = self.config
        if cfg.single_ocean_mode:
            return False
        if surface_y >= cfg.sea_level:
            return False

        max_gap = 4
        left_ocean_nearby = False
        right_ocean_nearby = False
        for offset in range(1, max_gap + 1):
            left_x = world_x - offset
            left_biome = self._biome_for_world_x(left_x)
            left_surface_y = self._terrain_height_for_world_x(left_x, biome=left_biome)
            if self._is_ocean_column_base(left_x, left_surface_y, biome=left_biome):
                left_ocean_nearby = True
                break

        for offset in range(1, max_gap + 1):
            right_x = world_x + offset
            right_biome = self._biome_for_world_x(right_x)
            right_surface_y = self._terrain_height_for_world_x(right_x, biome=right_biome)
            if self._is_ocean_column_base(right_x, right_surface_y, biome=right_biome):
                right_ocean_nearby = True
                break

        return left_ocean_nearby and right_ocean_nearby

    def _is_ocean_column_base(self, world_x: int, surface_y: int, biome: BiomeDefinition | None = None) -> bool:
        """Basisregel fuer Ocean-Spalten ohne Nachbarschaftsglaettung."""
        selected_biome = biome or self._biome_for_world_x(world_x)
        cfg = self.config
        if surface_y >= cfg.sea_level:
            return False

        if selected_biome.is_ocean:
            return True

        if cfg.single_ocean_mode:
            return False

        depth = min(1.0, max(0.0, (cfg.sea_level - surface_y) / 14.0))
        if depth < 0.72:
            return False

        ocean_mask = self._value_noise_2d(world_x, cfg.sea_level, cell_size=220, salt=1601)
        left_mask = self._value_noise_2d(world_x - 32, cfg.sea_level, cell_size=220, salt=1601)
        right_mask = self._value_noise_2d(world_x + 32, cfg.sea_level, cell_size=220, salt=1601)
        if ocean_mask <= left_mask or ocean_mask < right_mask:
            return False

        coastal_detail = self._value_noise_2d(world_x, cfg.sea_level, cell_size=44, salt=1603)
        threshold = 0.90 - 0.10 * depth
        return (ocean_mask + 0.05 * coastal_detail) > threshold

    def _settle_generated_falling_blocks(self, chunk: "Chunk", chunk_x: int) -> None:
        """Simuliert Fallbloecke waehrend der Chunk-Generierung bis zur lokalen Ruhe."""

        max_ticks = 32
        slide_decisions: dict[tuple[int, int], tuple[int, int, int]] = {}
        for tick in range(max_ticks):
            moved_any = False

            active_positions: set[tuple[int, int]] = set()
            for y in range(1, chunk.height):
                for local_x in range(chunk.width):
                    block_id = chunk.get_block(local_x, y)
                    if block_id != AIR and is_block_falling(block_id):
                        active_positions.add((local_x, y))

            if slide_decisions:
                slide_decisions = {
                    pos: signature
                    for pos, signature in slide_decisions.items()
                    if pos in active_positions
                }

            for y in range(1, chunk.height):
                for local_x in range(chunk.width):
                    block_id = chunk.get_block(local_x, y)
                    if block_id == AIR or not is_block_falling(block_id):
                        continue

                    below_y = y - 1
                    if chunk.get_block(local_x, below_y) == AIR:
                        chunk.set_block(local_x, y, AIR)
                        chunk.set_block(local_x, below_y, block_id)
                        moved_any = True
                        slide_decisions.pop((local_x, y), None)
                        continue

                    left_depth = -1
                    right_depth = -1
                    candidates: list[tuple[int, int]] = []
                    for dx in (-1, 1):
                        nx = local_x + dx
                        if nx < 0 or nx >= chunk.width:
                            continue
                        if chunk.get_block(nx, y) != AIR:
                            continue
                        if chunk.get_block(nx, below_y) != AIR:
                            continue
                        depth = sand_local_fall_depth(chunk.get_block, nx, below_y, air_block_id=AIR)
                        candidates.append((depth, dx))
                        if dx < 0:
                            left_depth = depth
                        else:
                            right_depth = depth

                    decision_key = (local_x, y)
                    decision_signature = sand_slide_decision_signature(
                        chunk.get_block(local_x, below_y),
                        left_depth,
                        right_depth,
                    )
                    if slide_decisions.get(decision_key) == decision_signature:
                        continue
                    slide_decisions[decision_key] = decision_signature

                    if not candidates:
                        continue

                    best_depth = max(score for score, _dx in candidates)
                    slide_chance = sand_slide_probability(best_depth)
                    world_x = chunk_x * CHUNK_WIDTH + local_x
                    roll = self._rand01_2d(world_x, y, salt=1733)
                    if roll >= slide_chance:
                        continue

                    best_dirs = [dx for score, dx in candidates if score == best_depth]
                    if len(best_dirs) == 1:
                        slide_dx = best_dirs[0]
                    else:
                        chooser = self._rand01_2d(world_x, y, salt=1777 + tick * 29)
                        slide_dx = best_dirs[0] if chooser < 0.5 else best_dirs[-1]

                    target_x = local_x + slide_dx
                    chunk.set_block(local_x, y, AIR)
                    chunk.set_block(target_x, below_y, block_id)
                    moved_any = True
                    slide_decisions.pop(decision_key, None)

            if not moved_any:
                break

    def generate_chunk(self, world: World, chunk_x: int):
        """Erzeugt einen deterministischen Chunk für eine gegebene Chunk-Koordinate."""
        if chunk_x in world.chunks:
            return world.chunks[chunk_x]

        cfg = self.config

        from world import Chunk

        saved_blocks = world.get_saved_chunk_blocks(chunk_x)
        if saved_blocks is not None:
            saved_water = world.get_saved_chunk_water(chunk_x) or {}
            saved_lava = world.get_saved_chunk_lava(chunk_x) or {}
            chunk = Chunk(chunk_x=chunk_x, blocks=saved_blocks, water=dict(saved_water), lava=dict(saved_lava))
            world.apply_pending_generated_blocks(chunk)
            world.chunks[chunk_x] = chunk
            return chunk

        chunk = Chunk(chunk_x=chunk_x)
        chunk_world_x_base = chunk_x * CHUNK_WIDTH

        def place_generated(world_x: int, y: int, block_id: int, replace_air_only: bool = False):
            if y < 0 or y >= WORLD_HEIGHT:
                return

            target_chunk_x, target_local_x = world_to_chunk_and_local(world_x)
            if target_chunk_x == chunk_x:
                if replace_air_only and chunk.get_block(target_local_x, y) != AIR:
                    return
                chunk.set_block(target_local_x, y, block_id)
                return

            if replace_air_only:
                neighbor_block = world.get_block(world_x, y, generate_if_missing=False)
                if neighbor_block != AIR:
                    return

            world.queue_generated_block(world_x, y, block_id)
        surface_heights: list[int] = [0] * chunk.width
        ocean_columns: list[bool] = [False] * chunk.width
        biome_columns: list[BiomeDefinition] = [self._biome_for_world_x(chunk_world_x_base + local_x) for local_x in range(chunk.width)]

        # Pass 1: Basis-Terrain fuer alle Spalten aufbauen.
        for local_x in range(chunk.width):
            biome = biome_columns[local_x]
            world_x = chunk_world_x_base + local_x
            base_height = self._terrain_height_for_world_x(world_x, biome=biome)
            is_ocean = self._is_ocean_column(world_x, base_height, biome=biome)
            height = self._ocean_island_surface_override(world_x, base_height, is_ocean)
            surface_heights[local_x] = height
            ocean_columns[local_x] = is_ocean
            is_coastal_band = cfg.sea_level <= height <= cfg.sea_level + cfg.coastal_beach_band
            coastal_sand_bias = self._rand01(world_x, salt=1231)
            surface_block_id = int(biome.surface_block_id)
            subsurface_block_id = int(biome.subsurface_block_id)
            deep_block_id = int(biome.deep_block_id)
            ocean_floor_block_id = int(biome.ocean_floor_block_id)
            for y in range(chunk.height):
                if y == 0:
                    block_id = BEDROCK
                elif y < height - 2:
                    if self._is_cave_air(world_x, y, height, biome_cave_density_multiplier=biome.cave_density_multiplier):
                        block_id = AIR
                    else:
                        if is_ocean and y >= height - 4:
                            block_id = ocean_floor_block_id
                        elif is_coastal_band and y >= height - 3 and coastal_sand_bias < 0.45:
                            block_id = ocean_floor_block_id
                        else:
                            block_id = self._pick_underground_block(
                                world_x,
                                y,
                                height,
                                base_block_id=deep_block_id,
                                biome_ore_density_multiplier=biome.ore_density_multiplier,
                            )
                elif y < height:
                    if is_ocean:
                        block_id = ocean_floor_block_id
                    elif is_coastal_band and y >= height - 1 and coastal_sand_bias < 0.62:
                        block_id = ocean_floor_block_id
                    else:
                        block_id = subsurface_block_id
                elif y == height:
                    block_id = ocean_floor_block_id if (is_ocean or (is_coastal_band and coastal_sand_bias < 0.74)) else surface_block_id
                else:
                    block_id = AIR
                chunk.set_block(local_x, y, block_id)

        # Pass 2: Baeume nachtraeglich setzen, damit Blaetter nicht ueberschrieben werden.
        for local_x in range(chunk.width):
            height = surface_heights[local_x]
            world_x = chunk_world_x_base + local_x
            biome = biome_columns[local_x]
            _terrain_amp, _detail_amp, _tree_density, rockiness = biome.profile.as_tuple()

            # Rocky-Biome: gelegentliche Felsformationen.
            outcrop_chance = 0.012 * rockiness
            if self._rand01(world_x, salt=503) < outcrop_chance:
                mound_height = 2 + int(self._rand01(world_x, salt=509) * 3)
                mound_radius = 1 + int(self._rand01(world_x, salt=521) * 2)
                base_y = height + 1
                for dx in range(-mound_radius, mound_radius + 1):
                    column_h = mound_height - abs(dx)
                    if column_h <= 0:
                        continue
                    if self._rand01(world_x + dx, salt=523) > 0.86:
                        column_h -= 1
                    for dy in range(max(1, column_h)):
                        place_generated(world_x + dx, base_y + dy, STONE, replace_air_only=True)

            # Seltene kleine Boulder auch ausserhalb von Rocky-Biomen.
            boulder_chance = 0.003 + 0.006 * rockiness
            if self._rand01(world_x, salt=541) < boulder_chance:
                boulder_h = 1 + int(self._rand01(world_x, salt=547) * 2)
                for dx in (-1, 0, 1):
                    if abs(dx) == 1 and self._rand01(world_x + dx, salt=551) > 0.7:
                        continue
                    for dy in range(max(1, boulder_h - abs(dx))):
                        place_generated(world_x + dx, height + 1 + dy, STONE, replace_air_only=True)

        # Pass 3: Sand-Patches unter der Erdoberflaeche als zusammenhaengende Taschen.
        for local_x in range(chunk.width):
            height = surface_heights[local_x]
            world_x = chunk_world_x_base + local_x
            if self._rand01(world_x, salt=901) > 0.28:
                continue

            patch_radius = 1 + int(self._rand01(world_x, salt=903) * 2)
            patch_height = 3 + int(self._rand01(world_x, salt=907) * 7)
            patch_base_y = max(6, height - 10 - int(self._rand01(world_x, salt=905) * 12))

            for dx in range(-patch_radius, patch_radius + 1):
                neighbor_world_x = world_x + dx
                neighbor_chunk_x, neighbor_local_x = world_to_chunk_and_local(neighbor_world_x)
                if neighbor_chunk_x != chunk_x:
                    continue

                for dy in range(patch_height):
                    target_y = patch_base_y + dy
                    if target_y >= height - 1 or target_y >= WORLD_HEIGHT - 1:
                        continue
                    if target_y <= 2:
                        continue
                    if self._rand01(neighbor_world_x + dy, salt=911) > 0.75:
                        continue

                    current_block = chunk.get_block(neighbor_local_x, target_y)
                    if current_block == AIR:
                        chunk.set_block(neighbor_local_x, target_y, SAND)

        for local_x in range(chunk.width):
            height = surface_heights[local_x]
            world_x = chunk_world_x_base + local_x
            biome = biome_columns[local_x]
            if height < cfg.sea_level:
                continue
            if not biome.allow_trees:
                continue
            if chunk.get_block(local_x, height) != biome.surface_block_id:
                continue
            if not self._has_tree(world_x, biome=biome):
                continue

            trunk_base_y = height + 1
            trunk_height = oak_trunk_height(self.seed, world_x)
            trunk_positions, leaf_positions, trunk_top = build_oak_tree_layout(
                world_x,
                trunk_base_y,
                trunk_height,
                WORLD_HEIGHT,
            )
            for tree_x, tree_y in trunk_positions:
                place_generated(tree_x, tree_y, OAK)

            leaves_center_y = trunk_top
            crown_radius_x = 2
            crown_down = 2
            crown_up = 1
            stretch_top = self._rand01(world_x, salt=73) > 0.78

            # Basisform aus shared tree-Layout.
            for leaf_x, leaf_y in leaf_positions:
                place_generated(leaf_x, leaf_y, LEAVES, replace_air_only=True)

            # Erweiterte Krone mit deterministischem Zufall für organischere Formen.
            for dx in range(-crown_radius_x, crown_radius_x + 1):
                for dy in range(-crown_down, crown_up + 1):
                    ly = leaves_center_y + dy
                    if ly < 0 or ly >= WORLD_HEIGHT:
                        continue

                    # Diamond-artige Basisform
                    dist = abs(dx) + abs(dy)
                    max_dist = crown_radius_x + (1 if dy < 0 else 0)
                    if dist > max_dist:
                        continue

                    # Außenbereich leicht ausdünnen, aber reproduzierbar.
                    edge = dist >= max_dist
                    if edge:
                        keep_chance = 0.82 + (0.05 if dy <= 0 else 0.0)
                        if self._rand01(world_x + dx * 17 + dy * 29, salt=79) > keep_chance:
                            continue

                    place_generated(world_x + dx, ly, LEAVES, replace_air_only=True)

            # Kleine, seltene Top-Variation statt stark wechselnder Kronenformen.
            top_leaf_y = leaves_center_y + crown_up + 1
            if 0 <= top_leaf_y < WORLD_HEIGHT:
                place_generated(world_x, top_leaf_y, LEAVES, replace_air_only=True)
            if stretch_top and 0 <= top_leaf_y + 1 < WORLD_HEIGHT:
                place_generated(world_x, top_leaf_y + 1, LEAVES, replace_air_only=True)
            if 0 <= top_leaf_y < WORLD_HEIGHT and self._rand01(world_x, salt=89) > 0.9:
                side = -1 if self._rand01(world_x, salt=97) < 0.5 else 1
                place_generated(world_x + side, top_leaf_y, LEAVES, replace_air_only=True)

        # Pass 3.5: Fallbloecke direkt waehrend der Generierung zur Ruhe bringen.
        self._settle_generated_falling_blocks(chunk, chunk_x)

        # Pass 4: Natuerliche Fluessigkeiten (Meeresspiegel + unterirdische Wasser/Lava-Taschen).
        for local_x in range(chunk.width):
            surface_y = surface_heights[local_x]
            world_x = chunk_world_x_base + local_x

            if ocean_columns[local_x]:
                for y in range(surface_y + 1, min(cfg.sea_level, WORLD_HEIGHT - 1) + 1):
                    if chunk.get_block(local_x, y) == AIR:
                        chunk.set_water(local_x, y, 1.0)

            underground_max_y = min(max(cfg.underground_water_max_y, cfg.underground_lava_max_y), WORLD_HEIGHT - 2)
            for y in range(4, underground_max_y + 1):
                if chunk.get_block(local_x, y) != AIR:
                    continue
                if chunk.get_water(local_x, y) > 0.0:
                    continue
                if chunk.get_lava(local_x, y) > 0.0:
                    continue

                below_block = chunk.get_block(local_x, y - 1)
                if below_block == AIR:
                    continue

                cave_signal = self._value_noise_2d(world_x, y, cell_size=10, salt=1181)
                pocket_signal = self._value_noise_2d(world_x, y, cell_size=22, salt=1193)
                if cave_signal <= cfg.cave_pocket_signal_threshold or pocket_signal <= cfg.cave_pocket_chamber_threshold:
                    continue

                liquid_type = self._pick_underground_liquid(world_x, y)
                if liquid_type == "lava":
                    chunk.set_lava(local_x, y, 1.0)
                elif liquid_type == "water":
                    chunk.set_water(local_x, y, 1.0)

        world.apply_pending_generated_blocks(chunk)
        world.chunks[chunk_x] = chunk
        return chunk

    def update_loaded_chunks(
        self,
        world: World,
        world_x: float,
        max_loads: int | None = None,
        max_unloads: int | None = None,
        keep_loaded_chunk_xs: set[int] | None = None,
    ):
        """Lädt/entlädt Chunks optional budgetiert und liefert (neu, entladen) zurück."""
        protected_chunks = keep_loaded_chunk_xs or set()
        current_chunk_x = int(world_x // TILE_SIZE) // CHUNK_WIDTH
        min_chunk_x = current_chunk_x - world.load_radius
        max_chunk_x = current_chunk_x + world.load_radius
        unloaded_chunks: list[int] = []
        loaded_chunks: list[int] = []

        unload_candidates: list[int] = []
        for chunk_x in world.chunks:
            if chunk_x in protected_chunks:
                continue
            if (chunk_x < min_chunk_x or chunk_x > max_chunk_x) and abs(chunk_x - current_chunk_x) > world.unload_radius:
                unload_candidates.append(chunk_x)

        unload_candidates.sort(key=lambda cx: abs(cx - current_chunk_x), reverse=True)
        if max_unloads is not None:
            unload_candidates = unload_candidates[: max(0, max_unloads)]

        for chunk_x in unload_candidates:
            chunk = world.chunks[chunk_x]
            world.save_chunk_blocks(chunk_x, chunk.blocks)
            world.save_chunk_water(chunk_x, chunk.water)
            world.save_chunk_lava(chunk_x, chunk.lava)
            del world.chunks[chunk_x]
            unloaded_chunks.append(chunk_x)

        if unloaded_chunks:
            world.water_system.deactivate_unloaded_chunks(set(world.chunks.keys()))
            world.lava_system.deactivate_unloaded_chunks(set(world.chunks.keys()))

        load_candidates = [chunk_x for chunk_x in range(min_chunk_x, max_chunk_x + 1) if chunk_x not in world.chunks]
        load_candidates.sort(key=lambda cx: abs(cx - current_chunk_x))
        if max_loads is not None:
            load_candidates = load_candidates[: max(0, max_loads)]

        for chunk_x in load_candidates:
            self.generate_chunk(world, chunk_x)
            loaded_chunks.append(chunk_x)
            world.water_system.activate_loaded_chunk_water(world, chunk_x)
            world.lava_system.activate_loaded_chunk_lava(world, chunk_x)

        return loaded_chunks, unloaded_chunks

    def get_surface_height(self, world: World, world_x: int) -> int:
        """Gibt die Bodenhöhe an einer Weltposition in Tile-Koordinaten zurück."""
        tile_x = int(world_x // TILE_SIZE)
        chunk_x, local_x = world_to_chunk_and_local(tile_x)
        self.generate_chunk(world, chunk_x)
        return self.terrain_height(chunk_x, local_x)


def build_world_sprite_list(
    world: World,
    center_world_x: float = 0.0,
    center_world_y: float = 0.0,
    view_width: float | None = None,
    view_height: float | None = None,
    margin_tiles: int = 4,
):
    """Erstellt eine SpriteList für sichtbare Blöcke im Weltkoordinatensystem."""
    sprite_list = arcade.SpriteList()

    if view_height is not None:
        half_h = view_height / 2
        min_tile_y = max(0, int((center_world_y - half_h) // TILE_SIZE) - margin_tiles)
        max_tile_y = min(WORLD_HEIGHT - 1, int((center_world_y + half_h) // TILE_SIZE) + margin_tiles)
    else:
        min_tile_y = 0
        max_tile_y = WORLD_HEIGHT - 1

    for chunk_x in sorted(world.chunks):
        chunk = world.chunks[chunk_x]
        chunk_sprites, _ = build_chunk_sprite_list(chunk_x, chunk, min_tile_y, max_tile_y)
        for sprite in chunk_sprites:
            sprite_list.append(sprite)

    return sprite_list


def get_water_render_height(level: float) -> float:
    """Returns quantized visible water height, with a separate rendering threshold."""
    normalized = max(0.0, min(1.0, float(level)))
    if normalized < WATER_RENDER_THRESHOLD:
        return 0.0
    visual_level = min(WATER_VISUAL_STEPS, max(1, math.ceil(normalized * WATER_VISUAL_STEPS)))
    return TILE_SIZE * (visual_level / WATER_VISUAL_STEPS)


def get_lava_render_height(level: float) -> float:
    """Returns quantized visible lava height, with a separate rendering threshold."""
    normalized = max(0.0, min(1.0, float(level)))
    if normalized < LAVA_RENDER_THRESHOLD:
        return 0.0
    visual_level = min(LAVA_VISUAL_STEPS, max(1, math.ceil(normalized * LAVA_VISUAL_STEPS)))
    return TILE_SIZE * (visual_level / LAVA_VISUAL_STEPS)


def build_chunk_sprite_list(chunk_x: int, chunk, min_tile_y: int, max_tile_y: int):
    """Erstellt nur feste Block-Sprites; Wasser wird separat als Overlay gerendert."""
    sprite_list = arcade.SpriteList()
    sprite_map: dict[tuple[int, int], arcade.Sprite] = {}
    min_y = max(0, min_tile_y)
    max_y = min(chunk.height - 1, max_tile_y)
    if min_y > max_y:
        return sprite_list, sprite_map

    for local_x in range(chunk.width):
        for y in range(min_y, max_y + 1):
            block_id = chunk.get_block(local_x, y)
            if block_id == AIR or block_id not in BLOCK_TEXTURES:
                continue

            sprite = arcade.Sprite(BLOCK_TEXTURES[block_id])
            sprite.center_x = (chunk_x * CHUNK_WIDTH + local_x + 0.5) * TILE_SIZE
            sprite.center_y = (y + 0.5) * TILE_SIZE
            sprite.width = TILE_SIZE
            sprite.height = TILE_SIZE
            sprite_list.append(sprite)
            sprite_map[(local_x, y)] = sprite

    return sprite_list, sprite_map


def build_chunk_water_sprite_list(chunk_x: int, chunk, min_tile_y: int, max_tile_y: int, include_map: bool = False):
    """Erstellt die Wasser-Overlay-Sprites für die sichtbare Welt."""
    sprite_list = arcade.SpriteList()
    sprite_map: dict[tuple[int, int], arcade.Sprite] = {}
    min_y = max(0, min_tile_y)
    max_y = min(chunk.height - 1, max_tile_y)
    if min_y > max_y:
        if include_map:
            return sprite_list, sprite_map
        return sprite_list

    for (local_x, y), level in sorted(chunk.water.items()):
        if y < min_y or y > max_y:
            continue

        block_id = chunk.get_block(local_x, y)
        if block_id != AIR and not is_block_water_passable(block_id):
            continue

        normalized = max(0.0, min(1.0, float(level)))
        height = get_water_render_height(normalized)
        if height <= 0.0 and normalized > 0.0:
            # Verhindert sichtbare "Luft-Lücken" in vertikalen Wassersträngen,
            # wenn nur Restmengen unterhalb der Render-Schwelle vorliegen.
            above = chunk.get_water(local_x, y + 1) if y + 1 < chunk.height else 0.0
            below = chunk.get_water(local_x, y - 1) if y - 1 >= 0 else 0.0
            if above >= WATER_RENDER_THRESHOLD or below >= WATER_RENDER_THRESHOLD:
                height = TILE_SIZE / WATER_VISUAL_STEPS
        if height <= 0.0:
            continue

        sprite = arcade.Sprite(WATER_TEXTURE)
        sprite.color = (120, 170, 255)
        sprite.alpha = 128
        sprite.width = TILE_SIZE
        sprite.height = height
        sprite.center_x = (chunk_x * CHUNK_WIDTH + local_x + 0.5) * TILE_SIZE
        sprite.center_y = (y + (height / TILE_SIZE) / 2.0) * TILE_SIZE
        sprite_list.append(sprite)
        sprite_map[(local_x, y)] = sprite

    if include_map:
        return sprite_list, sprite_map
    return sprite_list


def build_chunk_lava_sprite_list(chunk_x: int, chunk, min_tile_y: int, max_tile_y: int, include_map: bool = False):
    """Erstellt die Lava-Overlay-Sprites für die sichtbare Welt."""
    sprite_list = arcade.SpriteList()
    sprite_map: dict[tuple[int, int], arcade.Sprite] = {}
    min_y = max(0, min_tile_y)
    max_y = min(chunk.height - 1, max_tile_y)
    if min_y > max_y:
        if include_map:
            return sprite_list, sprite_map
        return sprite_list

    for (local_x, y), level in sorted(chunk.lava.items()):
        if y < min_y or y > max_y:
            continue

        block_id = chunk.get_block(local_x, y)
        if block_id != AIR and not is_block_water_passable(block_id):
            continue

        normalized = max(0.0, min(1.0, float(level)))
        height = get_lava_render_height(normalized)
        if height <= 0.0:
            continue

        sprite = arcade.Sprite(LAVA_TEXTURE)
        sprite.color = (255, 255, 255)
        sprite.alpha = 200
        sprite.width = TILE_SIZE
        sprite.height = height
        sprite.center_x = (chunk_x * CHUNK_WIDTH + local_x + 0.5) * TILE_SIZE
        sprite.center_y = (y + (height / TILE_SIZE) / 2.0) * TILE_SIZE
        sprite_list.append(sprite)
        sprite_map[(local_x, y)] = sprite

    if include_map:
        return sprite_list, sprite_map
    return sprite_list

