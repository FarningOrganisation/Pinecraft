"""Deterministische Terrain-Generierung für Pinecraft.

Dieses Modul enthält nur die prozedurale Erzeugung der Welt.
Die Welt-Daten selbst liegen in world.py.
"""

from __future__ import annotations

import math

import arcade

from blocks import AIR, BLOCK_TEXTURES, DIRT, GRASS, STONE
from settings import CHUNK_WIDTH, TILE_SIZE, WORLD_HEIGHT
from world import World, world_to_chunk_and_local


class WorldGenerator:
    """Erzeugt deterministisches Terrain für einen World-Container."""

    def __init__(self, seed: int = 1337):
        self.seed = seed

    def terrain_height(self, chunk_x: int, local_x: int) -> int:
        """Erzeugt einen stabilen, wiederholbaren Höhenwert mit Sinuswellen."""
        world_x = chunk_x * CHUNK_WIDTH + local_x
        height = (
            8
            + math.sin((world_x + self.seed) * 0.45) * 3.0
            + math.cos((world_x + self.seed) * 0.12) * 2.5
        )
        return max(4, min(WORLD_HEIGHT - 2, int(height)))

    def generate_chunk(self, world: World, chunk_x: int):
        """Erzeugt einen deterministischen Chunk für eine gegebene Chunk-Koordinate."""
        if chunk_x in world.chunks:
            return world.chunks[chunk_x]

        from world import Chunk

        chunk = Chunk(chunk_x=chunk_x)
        for local_x in range(chunk.width):
            height = self.terrain_height(chunk_x, local_x)
            for y in range(chunk.height):
                if y < height - 2:
                    block_id = STONE
                elif y < height:
                    block_id = DIRT
                elif y == height:
                    block_id = GRASS
                else:
                    block_id = AIR
                chunk.set_block(local_x, y, block_id)

        world.chunks[chunk_x] = chunk
        return chunk

    def update_loaded_chunks(self, world: World, world_x: float):
        """Lädt nur Chunks im aktiven Radius um den Spieler und entfernt entfernte."""
        current_chunk_x = int(world_x // TILE_SIZE) // CHUNK_WIDTH
        min_chunk_x = current_chunk_x - world.load_radius
        max_chunk_x = current_chunk_x + world.load_radius

        for chunk_x in list(world.chunks):
            if chunk_x < min_chunk_x or chunk_x > max_chunk_x:
                if abs(chunk_x - current_chunk_x) > world.unload_radius:
                    del world.chunks[chunk_x]

        for chunk_x in range(min_chunk_x, max_chunk_x + 1):
            self.generate_chunk(world, chunk_x)

    def get_surface_height(self, world: World, world_x: int) -> int:
        """Gibt die Bodenhöhe an einer Weltposition in Tile-Koordinaten zurück."""
        tile_x = int(world_x // TILE_SIZE)
        chunk_x, local_x = world_to_chunk_and_local(tile_x)
        self.generate_chunk(world, chunk_x)
        return self.terrain_height(chunk_x, local_x)


def build_world_sprite_list(world: World, center_world_x: float = 0.0, radius: int = 3):
    """Erstellt eine SpriteList mit allen aktuell geladenen Blöcken im Weltkoordinatensystem."""
    sprite_list = arcade.SpriteList()

    for chunk_x in sorted(world.chunks):
        chunk = world.chunks[chunk_x]
        for local_x in range(chunk.width):
            for y in range(chunk.height):
                block_id = chunk.get_block(local_x, y)
                if block_id == AIR or block_id not in BLOCK_TEXTURES:
                    continue

                sprite = arcade.Sprite(BLOCK_TEXTURES[block_id])
                sprite.center_x = (chunk_x * CHUNK_WIDTH + local_x + 0.5) * TILE_SIZE
                sprite.center_y = (y + 0.5) * TILE_SIZE
                sprite.width = TILE_SIZE
                sprite.height = TILE_SIZE
                sprite_list.append(sprite)

    return sprite_list

