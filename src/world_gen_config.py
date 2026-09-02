"""Konfigurierbare Parameter fuer die Weltgenerierung.

Diese Datei ist bewusst als zentrale Stellschraube gedacht.
Studierende koennen hier Werte anpassen, ohne die Core-Algorithmen in
world_generation.py selbst zu veraendern.
"""

from __future__ import annotations

from dataclasses import dataclass

from ids import DIRT, GRASS, SAND, STONE


@dataclass(frozen=True)
class BiomeProfile:
    """Profile-Werte fuer ein Biome.

    terrain_amp: Grobe Hoehenunterschiede
    detail_amp: Feinere Wellen
    tree_density: Baumhaeufigkeit
    rockiness: Anteil felsiger Formen
    """

    terrain_amp: float
    detail_amp: float
    tree_density: float
    rockiness: float

    def as_tuple(self) -> tuple[float, float, float, float]:
        return self.terrain_amp, self.detail_amp, self.tree_density, self.rockiness


@dataclass(frozen=True)
class BiomeDefinition:
    """Definiert ein einzelnes Biome inklusive Block-Palette und Gewichtung."""

    name: str
    weight: float
    profile: BiomeProfile
    surface_block_id: int = GRASS
    subsurface_block_id: int = DIRT
    deep_block_id: int = STONE
    ocean_floor_block_id: int = SAND
    height_bias: float = 0.0
    is_ocean: bool = False
    allow_trees: bool = True
    cave_density_multiplier: float = 1.0
    ore_density_multiplier: float = 1.0


@dataclass(frozen=True)
class WorldGenConfig:
    """Parameter fuer Terrain, Biome, Erze, Hoehlen und Fluessigkeiten."""

    biome_noise_cell_size: int = 176
    single_ocean_mode: bool = True
    single_ocean_center_x: int = 0
    single_ocean_width: int = -1
    ocean_islands_enabled: bool = True
    ocean_island_cell_size: int = 96
    ocean_island_threshold: float = 0.86
    ocean_island_min_radius: int = 3
    ocean_island_max_radius: int = 8
    ocean_island_min_peak_above_sea: int = 2
    ocean_island_max_peak_above_sea: int = 7
    ocean_zone_cell_size: int = 640
    ocean_zone_threshold: float = -1.0

    biomes: tuple[BiomeDefinition, ...] = (
        BiomeDefinition(
            name="plains",
            weight=3.0,
            profile=BiomeProfile(0.62, 0.45, 1.15, 0.15),
            surface_block_id=GRASS,
            subsurface_block_id=DIRT,
            deep_block_id=STONE,
            ocean_floor_block_id=SAND,
            height_bias=0.0,
            is_ocean=False,
            allow_trees=True,
            cave_density_multiplier=1.0,
            ore_density_multiplier=1.0,
        ),
        BiomeDefinition(
            name="mixed",
            weight=4.0,
            profile=BiomeProfile(0.82, 0.55, 0.90, 0.45),
            surface_block_id=GRASS,
            subsurface_block_id=DIRT,
            deep_block_id=STONE,
            ocean_floor_block_id=SAND,
            height_bias=0.0,
            is_ocean=False,
            allow_trees=True,
            cave_density_multiplier=1.0,
            ore_density_multiplier=1.0,
        ),
        BiomeDefinition(
            name="rocky",
            weight=2.0,
            profile=BiomeProfile(1.00, 0.65, 0.58, 1.00),
            surface_block_id=GRASS,
            subsurface_block_id=DIRT,
            deep_block_id=STONE,
            ocean_floor_block_id=SAND,
            height_bias=1.0,
            is_ocean=False,
            allow_trees=True,
            cave_density_multiplier=1.0,
            ore_density_multiplier=1.0,
        ),
        BiomeDefinition(
            name="mountain",
            weight=1.4,
            profile=BiomeProfile(1.35, 0.72, 0.42, 1.15),
            surface_block_id=GRASS,
            subsurface_block_id=DIRT,
            deep_block_id=STONE,
            ocean_floor_block_id=SAND,
            height_bias=3.0,
            is_ocean=False,
            allow_trees=True,
            cave_density_multiplier=1.0,
            ore_density_multiplier=1.0,
        ),
        BiomeDefinition(
            name="ocean",
            weight=2.2,
            profile=BiomeProfile(0.45, 0.30, 0.0, 0.08),
            surface_block_id=SAND,
            subsurface_block_id=SAND,
            deep_block_id=STONE,
            ocean_floor_block_id=SAND,
            height_bias=-18.0,
            is_ocean=True,
            allow_trees=False,
            cave_density_multiplier=1.0,
            ore_density_multiplier=1.0,
        ),
    )

    sea_level: int = 130
    coastal_beach_band: int = 2

    underground_water_max_y: int = 102
    underground_water_preferred_y: int = 72
    underground_water_preferred_half_span: int = 36
    underground_lava_max_y: int = 86
    underground_lava_min_y: int = 6

    cave_min_depth: int = 6
    cave_depth_span: float = 68.0
    cave_tunnel_base_threshold: float = 0.11
    cave_tunnel_depth_bonus: float = 0.075
    cave_chamber_base_threshold: float = 0.80
    cave_chamber_depth_bonus: float = 0.12
    cave_chamber_signal_base: float = 0.22
    cave_chamber_signal_depth_bonus: float = 0.04
    cave_density_multiplier: float = 1.0

    cave_pocket_signal_threshold: float = 0.66
    cave_pocket_chamber_threshold: float = 0.56

    ore_depth_span: float = 72.0
    ore_density_multiplier: float = 1.0
    coal_base_chance: float = 0.008
    coal_depth_bonus: float = 0.030
    iron_base_chance: float = 0.007
    iron_depth_bonus: float = 0.028
    gold_base_chance: float = 0.0008
    gold_depth_bonus: float = 0.0065
    diamond_base_chance: float = 0.00025
    diamond_depth_bonus: float = 0.0035
    gold_max_y_ratio: float = 0.25
    diamond_max_y_ratio: float = 0.16


DEFAULT_WORLD_GEN_CONFIG = WorldGenConfig()


def normalized_biome_probabilities(config: WorldGenConfig) -> list[tuple[BiomeDefinition, float]]:
    """Liefert Biome mit normalisierten Wahrscheinlichkeiten aus den Gewichten."""
    positive = [(biome, float(biome.weight)) for biome in config.biomes if float(biome.weight) > 0.0]
    if not positive:
        return []

    total = sum(weight for _biome, weight in positive)
    if total <= 0.0:
        return []

    return [(biome, weight / total) for biome, weight in positive]


def get_biome_by_name(config: WorldGenConfig, biome_name: str) -> BiomeDefinition | None:
    """Sucht ein Biome in der Config ueber seinen Namen."""
    target = str(biome_name).strip().lower()
    for biome in config.biomes:
        if biome.name.strip().lower() == target:
            return biome
    return None


def validate_world_gen_config(config: WorldGenConfig) -> list[str]:
    """Gibt fruehe Hinweise bei auffaelligen Konfigurationswerten zurueck."""
    hints: list[str] = []

    if config.biome_noise_cell_size < 8:
        hints.append("biome_noise_cell_size sollte mindestens 8 sein.")

    if config.single_ocean_mode:
        if config.single_ocean_width != -1 and config.single_ocean_width < 8:
            hints.append("single_ocean_width muss -1 (biome width) oder mindestens 8 sein.")
    else:
        if config.ocean_zone_cell_size < 64:
            hints.append("ocean_zone_cell_size sollte mindestens 64 sein.")
        if config.ocean_zone_threshold != -1.0 and not (0.0 <= config.ocean_zone_threshold <= 1.0):
            hints.append("ocean_zone_threshold muss -1.0 (auto) oder im Bereich [0.0, 1.0] sein.")

    if config.ocean_island_cell_size < 24:
        hints.append("ocean_island_cell_size sollte mindestens 24 sein.")
    if not (0.0 <= config.ocean_island_threshold <= 1.0):
        hints.append("ocean_island_threshold sollte im Bereich [0.0, 1.0] liegen.")
    if config.ocean_island_min_radius < 1:
        hints.append("ocean_island_min_radius sollte mindestens 1 sein.")
    if config.ocean_island_max_radius < config.ocean_island_min_radius:
        hints.append("ocean_island_max_radius sollte >= ocean_island_min_radius sein.")
    if config.ocean_island_min_peak_above_sea < 1:
        hints.append("ocean_island_min_peak_above_sea sollte mindestens 1 sein.")
    if config.ocean_island_max_peak_above_sea < config.ocean_island_min_peak_above_sea:
        hints.append("ocean_island_max_peak_above_sea sollte >= ocean_island_min_peak_above_sea sein.")

    if not config.biomes:
        hints.append("Mindestens ein Biome muss definiert sein.")
    else:
        if not normalized_biome_probabilities(config):
            hints.append("Mindestens ein Biome-Gewicht muss > 0 sein.")

        seen_names: set[str] = set()
        has_ocean_biome = False
        for biome in config.biomes:
            normalized_name = biome.name.strip().lower()
            if not normalized_name:
                hints.append("Biome ohne Namen gefunden.")
            elif normalized_name in seen_names:
                hints.append(f"Biome-Name '{biome.name}' ist doppelt vorhanden.")
            else:
                seen_names.add(normalized_name)

            if biome.is_ocean:
                has_ocean_biome = True

            if biome.weight < 0.0:
                hints.append(f"Biome '{biome.name}': weight sollte >= 0 sein.")

            for label, block_id in (
                ("surface_block_id", biome.surface_block_id),
                ("subsurface_block_id", biome.subsurface_block_id),
                ("deep_block_id", biome.deep_block_id),
                ("ocean_floor_block_id", biome.ocean_floor_block_id),
            ):
                if not isinstance(block_id, int):
                    hints.append(f"Biome '{biome.name}': {label} sollte eine int-ID sein.")

            if biome.cave_density_multiplier <= 0.0:
                hints.append(f"Biome '{biome.name}': cave_density_multiplier sollte > 0 sein.")
            if biome.ore_density_multiplier <= 0.0:
                hints.append(f"Biome '{biome.name}': ore_density_multiplier sollte > 0 sein.")

        if not has_ocean_biome:
            hints.append("Es ist kein Ocean-Biome definiert (is_ocean=True).")

    if config.cave_density_multiplier <= 0.0:
        hints.append("cave_density_multiplier sollte > 0 sein.")
    if config.ore_density_multiplier <= 0.0:
        hints.append("ore_density_multiplier sollte > 0 sein.")
    if config.cave_min_depth < 1:
        hints.append("cave_min_depth sollte mindestens 1 sein.")
    if config.cave_depth_span <= 0.0:
        hints.append("cave_depth_span sollte > 0 sein.")
    if config.ore_depth_span <= 0.0:
        hints.append("ore_depth_span sollte > 0 sein.")
    if config.underground_lava_min_y >= config.underground_lava_max_y:
        hints.append("underground_lava_min_y sollte kleiner als underground_lava_max_y sein.")
    if config.sea_level <= 0:
        hints.append("sea_level sollte > 0 sein.")

    return hints
