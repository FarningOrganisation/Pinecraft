"""Deterministische Terrain-Generierung für Pinecraft.

Dieses Modul enthält nur die prozedurale Erzeugung der Welt.
Die Welt-Daten selbst liegen in world.py.
"""

from __future__ import annotations

import math

import arcade

from blocks import (
    AIR,
    BEDROCK,
    BLOCK_TEXTURES,
    COAL_ORE,
    DIAMOND_ORE,
    DIRT,
    GOLD_ORE,
    GRASS,
    IRON_ORE,
    LEAVES,
    OAK,
    STONE,
)
from settings import CHUNK_WIDTH, TILE_SIZE, WORLD_HEIGHT
from world import World, world_to_chunk_and_local


class WorldGenerator:
    """Erzeugt deterministisches Terrain für einen World-Container."""

    def __init__(self, seed: int = 1337):
        self.seed = seed

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

    def _pick_underground_block(self, world_x: int, y: int, surface_y: int) -> int:
        """Wählt für tiefe Steinbereiche deterministisch passende Erze aus."""
        depth_from_surface = max(0, surface_y - y)
        if depth_from_surface < 4:
            return STONE

        # Mehr Erze in größerer Tiefe.
        depth_factor = min(1.0, max(0.0, (depth_from_surface - 4) / 72.0))

        # Grobe 2D-Patches (vein-artig), ohne teuren Noise-Overhead.
        patch_x = world_x // 4
        patch_y = y // 3
        richness = 0.7 + 0.7 * self._rand01_2d(patch_x, patch_y, salt=719)

        # Insgesamt weniger Erze; Kohle und Eisen in aehnlicher Hauefigkeit.
        coal_chance = (0.008 + 0.030 * depth_factor) * richness
        iron_chance = (0.007 + 0.028 * depth_factor) * richness

        very_deep_limit = int(WORLD_HEIGHT * 0.25)
        ultra_deep_limit = int(WORLD_HEIGHT * 0.16)
        gold_chance = 0.0
        diamond_chance = 0.0
        if y <= very_deep_limit:
            gold_chance = (0.0008 + 0.0065 * depth_factor) * richness
        if y <= ultra_deep_limit:
            diamond_chance = (0.00025 + 0.0035 * depth_factor) * richness

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
        return STONE

    def _biome_value(self, world_x: int) -> float:
        """Langsame Biome-Kurve in etwa [-1, 1]."""
        low = math.sin((world_x + self.seed) * 0.0038)
        mid = math.cos((world_x - self.seed) * 0.0019)
        band = int(world_x // 28)
        step = (self._rand01(band, salt=211) - 0.5) * 0.22
        return max(-1.0, min(1.0, low * 0.62 + mid * 0.38 + step))

    def _biome_profile(self, world_x: int) -> tuple[float, float, float, float]:
        """Gibt (terrain_amp, detail_amp, tree_density, rockiness) zurück."""
        biome = self._biome_value(world_x)
        if biome < -0.2:
            # Plains: eher glatt, mehr Grasland und Bäume.
            return 0.62, 0.45, 1.15, 0.15
        if biome > 0.62:
            # Mountain: hohe Silhouetten, weniger Bäume, steiniger.
            return 1.35, 0.72, 0.42, 1.15
        if biome > 0.38:
            # Rocky: etwas steiniger, weniger Bäume, mehr Artefakte.
            return 1.0, 0.65, 0.58, 1.0
        # Mixed/Hills: Mittelweg.
        return 0.82, 0.55, 0.9, 0.45

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
        base_height = WORLD_HEIGHT // 2
        biome = self._biome_value(world_x)
        terrain_amp, detail_amp, _tree_density, _rockiness = self._biome_profile(world_x)

        large_wave = math.sin((world_x + self.seed) * 0.036) * 9.0 * terrain_amp
        medium_wave = math.cos((world_x + self.seed) * 0.010) * 6.0 * terrain_amp
        small_wave = math.sin((world_x + self.seed) * 0.075) * 1.6 * detail_amp
        detail_wave = math.cos((world_x + self.seed) * 0.15) * 0.8 * detail_amp

        # Leichter Jitter gegen zu glatte Kanten, aber bewusst dezent.
        jitter = (self._rand01(world_x, salt=31) - 0.5) * 1.0 * detail_amp

        height = (
            base_height
            + large_wave
            + medium_wave
            + small_wave
            + detail_wave
            + jitter
        )

        # Seltene hohe Berge ueber Makro-Zonen, dazwischen bleibt es glatt.
        height += self._mountain_peak_add(world_x)

        return max(8, min(WORLD_HEIGHT - 2, int(height)))

    def _has_tree(self, world_x: int) -> bool:
        """Deterministische Baumverteilung entlang der X-Achse."""
        _terrain_amp, _detail_amp, tree_density, _rockiness = self._biome_profile(world_x)
        value = (world_x * 73856093 + self.seed * 19349663) & 0xFFFFFFFF
        base_tree = value % 17 == 0
        if not base_tree:
            return False
        return self._rand01(world_x, salt=401) < min(1.0, tree_density)

    def _tree_height(self, world_x: int) -> int:
        """Deterministische Stammhöhe zwischen 4 und 6."""
        value = (world_x * 83492791 + self.seed * 2971215073) & 0xFFFFFFFF
        return 4 + (value % 3)

    def generate_chunk(self, world: World, chunk_x: int):
        """Erzeugt einen deterministischen Chunk für eine gegebene Chunk-Koordinate."""
        if chunk_x in world.chunks:
            return world.chunks[chunk_x]

        from world import Chunk

        saved_blocks = world.get_saved_chunk_blocks(chunk_x)
        if saved_blocks is not None:
            chunk = Chunk(chunk_x=chunk_x, blocks=saved_blocks)
            world.apply_pending_generated_blocks(chunk)
            world.chunks[chunk_x] = chunk
            return chunk

        chunk = Chunk(chunk_x=chunk_x)

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

        # Pass 1: Basis-Terrain fuer alle Spalten aufbauen.
        for local_x in range(chunk.width):
            height = self.terrain_height(chunk_x, local_x)
            surface_heights[local_x] = height
            world_x = chunk_x * CHUNK_WIDTH + local_x
            for y in range(chunk.height):
                if y == 0:
                    block_id = BEDROCK
                elif y < height - 2:
                    block_id = self._pick_underground_block(world_x, y, height)
                elif y < height:
                    block_id = DIRT
                elif y == height:
                    block_id = GRASS
                else:
                    block_id = AIR
                chunk.set_block(local_x, y, block_id)

        # Pass 2: Baeume nachtraeglich setzen, damit Blaetter nicht ueberschrieben werden.
        for local_x in range(chunk.width):
            height = surface_heights[local_x]
            world_x = chunk_x * CHUNK_WIDTH + local_x
            _terrain_amp, _detail_amp, _tree_density, rockiness = self._biome_profile(world_x)

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

        for local_x in range(chunk.width):
            height = surface_heights[local_x]
            world_x = chunk_x * CHUNK_WIDTH + local_x
            if not self._has_tree(world_x):
                continue

            trunk_base_y = height + 1
            trunk_height = self._tree_height(world_x)
            trunk_top = min(WORLD_HEIGHT - 1, trunk_base_y + trunk_height - 1)

            for tree_y in range(trunk_base_y, trunk_top + 1):
                place_generated(world_x, tree_y, OAK)

            leaves_center_y = trunk_top
            crown_radius_x = 2
            crown_down = 2
            crown_up = 1
            stretch_top = self._rand01(world_x, salt=73) > 0.78

            # Garantierte Kern-Krone, damit kein kahler Baum entsteht.
            core_offsets = [
                (0, 0),
                (0, 1),
                (0, -1),
                (1, 0),
                (-1, 0),
            ]
            for dx, dy in core_offsets:
                ly = leaves_center_y + dy
                place_generated(world_x + dx, ly, LEAVES, replace_air_only=True)

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

        world.apply_pending_generated_blocks(chunk)
        world.chunks[chunk_x] = chunk
        return chunk

    def update_loaded_chunks(
        self,
        world: World,
        world_x: float,
        max_loads: int | None = None,
        max_unloads: int | None = None,
    ):
        """Lädt/entlädt Chunks optional budgetiert und liefert (neu, entladen) zurück."""
        current_chunk_x = int(world_x // TILE_SIZE) // CHUNK_WIDTH
        min_chunk_x = current_chunk_x - world.load_radius
        max_chunk_x = current_chunk_x + world.load_radius
        unloaded_chunks: list[int] = []
        loaded_chunks: list[int] = []

        unload_candidates: list[int] = []
        for chunk_x in world.chunks:
            if (chunk_x < min_chunk_x or chunk_x > max_chunk_x) and abs(chunk_x - current_chunk_x) > world.unload_radius:
                unload_candidates.append(chunk_x)

        unload_candidates.sort(key=lambda cx: abs(cx - current_chunk_x), reverse=True)
        if max_unloads is not None:
            unload_candidates = unload_candidates[: max(0, max_unloads)]

        for chunk_x in unload_candidates:
            world.save_chunk_blocks(chunk_x, world.chunks[chunk_x].blocks)
            del world.chunks[chunk_x]
            unloaded_chunks.append(chunk_x)

        load_candidates = [chunk_x for chunk_x in range(min_chunk_x, max_chunk_x + 1) if chunk_x not in world.chunks]
        load_candidates.sort(key=lambda cx: abs(cx - current_chunk_x))
        if max_loads is not None:
            load_candidates = load_candidates[: max(0, max_loads)]

        for chunk_x in load_candidates:
            self.generate_chunk(world, chunk_x)
            loaded_chunks.append(chunk_x)

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


def build_chunk_sprite_list(chunk_x: int, chunk, min_tile_y: int, max_tile_y: int):
    """Erstellt Sprites und Sprite-Index für einen Chunk im Y-Bereich."""
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

