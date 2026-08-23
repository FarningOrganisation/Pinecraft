"""Weltmodell für Pinecraft.

Dieses Modul enthält nur den eigentlichen Weltzustand und die
Block-Operationen. Die prozedurale Generierung der Terrain-Höhen liegt in
world_generation.py.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from blocks import AIR
from settings import CHUNK_WIDTH, TILE_SIZE, WORLD_HEIGHT


def world_to_chunk_and_local(world_x: int) -> tuple[int, int]:
    """Konvertiert eine Tile-Koordinate in Chunk- und lokale Position."""
    chunk_x, local_x = divmod(world_x, CHUNK_WIDTH)
    if local_x < 0:
        chunk_x -= 1
        local_x += CHUNK_WIDTH
    return chunk_x, local_x


@dataclass
class Chunk:
    """Ein Chunk enthält eine feste Anzahl an Blöcken pro Zeile."""

    chunk_x: int
    width: int = CHUNK_WIDTH
    height: int = WORLD_HEIGHT
    blocks: list[list[int]] = field(default_factory=list)

    def __post_init__(self):
        if not self.blocks:
            self.blocks = [[AIR for _ in range(self.width)] for _ in range(self.height)]

    def get_block(self, local_x: int, y: int) -> int:
        """Liefert den Block an einer Position im Chunk."""
        if 0 <= local_x < self.width and 0 <= y < self.height:
            return self.blocks[y][local_x]
        return AIR

    def set_block(self, local_x: int, y: int, block_id: int) -> None:
        """Setzt einen Block in diesem Chunk."""
        if 0 <= local_x < self.width and 0 <= y < self.height:
            self.blocks[y][local_x] = block_id


class World:
    """Objekt, das den aktuellen Zustand der Welt verwaltet."""

    def __init__(self, seed: int = 1337, load_radius: int = 4, unload_radius: int = 6, generator=None):
        self.seed = seed
        self.chunks: dict[int, Chunk] = {}
        self.load_radius = load_radius
        self.unload_radius = unload_radius

        if generator is None:
            from world_generation import WorldGenerator

            self.generator = WorldGenerator(seed=seed)
        else:
            self.generator = generator

    def generate_chunk(self, chunk_x: int) -> Chunk:
        """Generiert oder lädt den angegebenen Chunk."""
        return self.generator.generate_chunk(self, chunk_x)

    def update_loaded_chunks(self, world_x: float):
        """Lädt nur Chunks im aktiven Radius um den Spieler."""
        self.generator.update_loaded_chunks(self, world_x)

    def get_loaded_chunk_count(self) -> int:
        """Gibt die Anzahl der aktuell geladenen Chunks zurück."""
        return len(self.chunks)

    def to_block_position(self, world_x: float, world_y: float) -> tuple[int, int]:
        """Konvertiert eine Weltposition in Block-Koordinaten."""
        return int(world_x // TILE_SIZE), int(world_y // TILE_SIZE)

    def to_world_position(self, block_x: int, block_y: int) -> tuple[float, float]:
        """Konvertiert eine Block-Koordinate in Weltposition (Block-Mitte)."""
        return (block_x + 0.5) * TILE_SIZE, (block_y + 0.5) * TILE_SIZE

    def get_surface_height(self, world_x: int) -> int:
        """Gibt die Bodenhöhe an einer Weltposition in Tile-Koordinaten zurück."""
        return self.generator.get_surface_height(self, world_x)

    def get_ground_top(self, world_x: int) -> float:
        """Gibt die Oberkante des Bodens an einer Weltposition in Pixeln zurück."""
        height = self.get_surface_height(world_x)
        return (height + 1) * TILE_SIZE

    def get_block(self, world_x: int, y: int) -> int:
        """Gibt einen Block an einer Weltposition zurück."""
        if y < 0 or y >= WORLD_HEIGHT:
            return AIR

        chunk_x, local_x = world_to_chunk_and_local(world_x)
        chunk = self.generate_chunk(chunk_x)
        return chunk.get_block(local_x, y)

    def set_block(self, world_x: int, y: int, block_id: int) -> None:
        """Setzt einen Block an einer Weltposition."""
        if y < 0 or y >= WORLD_HEIGHT:
            return

        chunk_x, local_x = world_to_chunk_and_local(world_x)
        chunk = self.generate_chunk(chunk_x)
        chunk.set_block(local_x, y, block_id)

    def break_block(self, world_x: int, y: int) -> int:
        """Entfernt einen Block und liefert den alten Blocktyp zurück."""
        block_id = self.get_block(world_x, y)
        if block_id == AIR:
            return AIR
        self.set_block(world_x, y, AIR)
        return block_id

    def place_block(self, world_x: int, y: int, block_id: int) -> bool:
        """Platziert einen Block, wenn die Position frei ist."""
        if self.get_block(world_x, y) != AIR:
            return False
        self.set_block(world_x, y, block_id)
        return True

    def get_blocks_around(self, left: float, right: float, bottom: float, top: float):
        """Liefert nur die festen Blöcke, die in der Nähe des AABBs liegen."""
        min_tile_x = int(math.floor(left / TILE_SIZE))
        max_tile_x = int(math.floor((right - 1e-6) / TILE_SIZE))
        min_tile_y = int(math.floor(bottom / TILE_SIZE))
        max_tile_y = int(math.floor((top - 1e-6) / TILE_SIZE))

        for tile_x in range(min_tile_x, max_tile_x + 1):
            for tile_y in range(min_tile_y, max_tile_y + 1):
                block_id = self.get_block(tile_x, tile_y)
                if block_id == AIR:
                    continue
                block_left = tile_x * TILE_SIZE
                block_right = block_left + TILE_SIZE
                block_bottom = tile_y * TILE_SIZE
                block_top = block_bottom + TILE_SIZE
                yield tile_x, tile_y, block_left, block_right, block_bottom, block_top
