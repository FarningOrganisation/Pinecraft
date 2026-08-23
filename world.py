"""Weltmodell für Pinecraft.

Dieses Modul enthält nur den eigentlichen Weltzustand und die
Block-Operationen. Die prozedurale Generierung der Terrain-Höhen liegt in
world_generation.py.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from blocks import AIR, is_block_solid
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

    def __init__(self, seed: int = 1337, load_radius: int = 3, unload_radius: int = 5, generator=None):
        self.seed = seed
        self.chunks: dict[int, Chunk] = {}
        self.placed_items: dict[tuple[int, int], int] = {}
        self.saved_chunk_blocks: dict[int, list[list[int]]] = {}
        self.pending_generated_blocks: dict[int, dict[tuple[int, int], int]] = {}
        self.changed_blocks: list[tuple[int, int, int, int]] = []
        self.changed_placed_items: list[tuple[int, int, int | None, int | None]] = []
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

    def get_saved_chunk_blocks(self, chunk_x: int) -> list[list[int]] | None:
        """Liefert gespeicherte Blockdaten für einen Chunk, falls vorhanden."""
        blocks = self.saved_chunk_blocks.get(chunk_x)
        if blocks is None:
            return None
        return [row[:] for row in blocks]

    def save_chunk_blocks(self, chunk_x: int, blocks: list[list[int]]) -> None:
        """Speichert einen Snapshot der Chunk-Blöcke persistent im Speicher."""
        self.saved_chunk_blocks[chunk_x] = [row[:] for row in blocks]

    def queue_generated_block(self, world_x: int, y: int, block_id: int) -> None:
        """Merkt Welt-Generierungsblöcke ohne Chunk-Generierung im aktuellen Frame."""
        if y < 0 or y >= WORLD_HEIGHT:
            return

        chunk_x, local_x = world_to_chunk_and_local(world_x)
        loaded_chunk = self.chunks.get(chunk_x)
        if loaded_chunk is not None:
            old_block_id = loaded_chunk.get_block(local_x, y)
            if old_block_id == block_id:
                return
            loaded_chunk.set_block(local_x, y, block_id)
            self.changed_blocks.append((world_x, y, old_block_id, block_id))
            return

        saved_blocks = self.saved_chunk_blocks.get(chunk_x)
        if saved_blocks is not None:
            saved_blocks[y][local_x] = block_id
            return

        pending = self.pending_generated_blocks.setdefault(chunk_x, {})
        pending[(local_x, y)] = block_id

    def apply_pending_generated_blocks(self, chunk: Chunk) -> None:
        """Überträgt geparkte Generierungsblöcke auf einen frisch erzeugten Chunk."""
        pending = self.pending_generated_blocks.pop(chunk.chunk_x, None)
        if not pending:
            return

        for (local_x, y), block_id in pending.items():
            chunk.set_block(local_x, y, block_id)

    def update_loaded_chunks(
        self,
        world_x: float,
        max_loads: int | None = None,
        max_unloads: int | None = None,
    ):
        """Lädt Chunks im Radius, optional mit Budget pro Aufruf."""
        return self.generator.update_loaded_chunks(self, world_x, max_loads=max_loads, max_unloads=max_unloads)

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

    def get_block(self, world_x: int, y: int, generate_if_missing: bool = True) -> int:
        """Gibt einen Block an einer Weltposition zurück."""
        if y < 0 or y >= WORLD_HEIGHT:
            return AIR

        chunk_x, local_x = world_to_chunk_and_local(world_x)
        if generate_if_missing:
            chunk = self.generate_chunk(chunk_x)
        else:
            chunk = self.chunks.get(chunk_x)
            if chunk is None:
                return AIR
        return chunk.get_block(local_x, y)

    def set_block(self, world_x: int, y: int, block_id: int) -> None:
        """Setzt einen Block an einer Weltposition."""
        if y < 0 or y >= WORLD_HEIGHT:
            return

        chunk_x, local_x = world_to_chunk_and_local(world_x)
        chunk = self.generate_chunk(chunk_x)
        old_block_id = chunk.get_block(local_x, y)
        if old_block_id == block_id:
            return
        chunk.set_block(local_x, y, block_id)
        self.changed_blocks.append((world_x, y, old_block_id, block_id))

    def consume_changed_blocks(self) -> list[tuple[int, int, int, int]]:
        """Liefert und leert die Liste geänderter Blöcke als (x, y, alt, neu)."""
        if not self.changed_blocks:
            return []
        changes = self.changed_blocks
        self.changed_blocks = []
        return changes

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
        if (world_x, y) in self.placed_items:
            return False
        self.set_block(world_x, y, block_id)
        return True

    def get_placed_item(self, world_x: int, y: int) -> int | None:
        """Liefert ein platziertes Item an einer Tile-Position oder None."""
        return self.placed_items.get((world_x, y))

    def place_item(self, world_x: int, y: int, item_id: int) -> bool:
        """Platziert ein Item in einer freien Blockzelle."""
        if y < 0 or y >= WORLD_HEIGHT:
            return False
        if self.get_block(world_x, y) != AIR:
            return False

        key = (world_x, y)
        old_item = self.placed_items.get(key)
        if old_item is not None:
            return False

        self.placed_items[key] = item_id
        self.changed_placed_items.append((world_x, y, None, item_id))
        return True

    def remove_placed_item(self, world_x: int, y: int) -> int | None:
        """Entfernt ein platziertes Item und liefert dessen ID."""
        key = (world_x, y)
        old_item = self.placed_items.pop(key, None)
        if old_item is None:
            return None
        self.changed_placed_items.append((world_x, y, old_item, None))
        return old_item

    def consume_changed_placed_items(self) -> list[tuple[int, int, int | None, int | None]]:
        """Liefert und leert die Liste geänderter platzierter Items."""
        if not self.changed_placed_items:
            return []
        changes = self.changed_placed_items
        self.changed_placed_items = []
        return changes

    def get_blocks_around(self, left: float, right: float, bottom: float, top: float):
        """Liefert nur die festen Blöcke, die in der Nähe des AABBs liegen."""
        min_tile_x = int(math.floor(left / TILE_SIZE))
        max_tile_x = int(math.floor((right - 1e-6) / TILE_SIZE))
        min_tile_y = int(math.floor(bottom / TILE_SIZE))
        max_tile_y = int(math.floor((top - 1e-6) / TILE_SIZE))

        for tile_x in range(min_tile_x, max_tile_x + 1):
            for tile_y in range(min_tile_y, max_tile_y + 1):
                block_id = self.get_block(tile_x, tile_y, generate_if_missing=False)
                if block_id == AIR or not is_block_solid(block_id):
                    continue
                block_left = tile_x * TILE_SIZE
                block_right = block_left + TILE_SIZE
                block_bottom = tile_y * TILE_SIZE
                block_top = block_bottom + TILE_SIZE
                yield tile_x, tile_y, block_left, block_right, block_bottom, block_top
