"""Sampling helpers for lava-based local lights."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from settings import CHUNK_WIDTH, TILE_SIZE

LAVA_LIGHT_MIN_AMOUNT = 0.02
LAVA_LIGHT_SAMPLE_SPACING = 3
MAX_LAVA_LIGHT_SAMPLES = 16
BASE_LAVA_LIGHT_RADIUS = 205.0


@dataclass(frozen=True)
class LavaLightSample:
    tile_x: int
    tile_y: int
    world_x: float
    world_y: float
    radius: float
    strength: float


def _is_boundary_lava_cell(world, tile_x: int, tile_y: int, min_volume: float) -> bool:
    """True, wenn die Zelle Lava-Rand ist (mindestens ein Kardinalnachbar ohne sinnvolle Lava)."""
    for nx, ny in ((tile_x - 1, tile_y), (tile_x + 1, tile_y), (tile_x, tile_y - 1), (tile_x, tile_y + 1)):
        if world.get_lava(nx, ny) < min_volume:
            return True
    return False


def _volume_to_radius_strength(amount: float, min_volume: float) -> tuple[float, float]:
    clamped_amount = min(1.0, max(0.0, amount))
    # Keep a tiny cutoff only to suppress floating-point residue noise.
    if clamped_amount < min_volume:
        return 0.0, 0.0

    strength = sqrt(clamped_amount)
    radius = BASE_LAVA_LIGHT_RADIUS * (0.4 + 0.6 * clamped_amount)
    return radius, strength


def collect_lava_light_samples(
    world,
    min_tile_x: int,
    max_tile_x: int,
    min_tile_y: int,
    max_tile_y: int,
    camera_world_x: float,
    camera_world_y: float,
    max_samples: int = MAX_LAVA_LIGHT_SAMPLES,
    sample_spacing: int = LAVA_LIGHT_SAMPLE_SPACING,
    min_volume: float = LAVA_LIGHT_MIN_AMOUNT,
) -> list[LavaLightSample]:
    """Collects sampled boundary lava lights in visible range, prioritized by camera distance."""
    if max_samples <= 0:
        return []

    spacing = max(1, int(sample_spacing))
    min_chunk_x = min_tile_x // CHUNK_WIDTH
    max_chunk_x = max_tile_x // CHUNK_WIDTH

    bucket_best: dict[tuple[int, int], tuple[float, int, int, float, float, float, float]] = {}

    for chunk_x in range(min_chunk_x, max_chunk_x + 1):
        chunk = world.chunks.get(chunk_x)
        if chunk is None or not chunk.lava:
            continue

        for (local_x, tile_y), amount in chunk.lava.items():
            if tile_y < min_tile_y or tile_y > max_tile_y:
                continue

            tile_x = chunk_x * CHUNK_WIDTH + local_x
            if tile_x < min_tile_x or tile_x > max_tile_x:
                continue
            if amount < min_volume:
                continue
            if not _is_boundary_lava_cell(world, tile_x, tile_y, min_volume):
                continue

            world_x = (tile_x + 0.5) * TILE_SIZE
            world_y = (tile_y + 0.5) * TILE_SIZE
            dist_sq = (world_x - camera_world_x) ** 2 + (world_y - camera_world_y) ** 2
            radius, strength = _volume_to_radius_strength(amount, min_volume)

            bucket = (tile_x // spacing, tile_y // spacing)
            previous = bucket_best.get(bucket)
            if previous is None or dist_sq < previous[0]:
                bucket_best[bucket] = (dist_sq, tile_x, tile_y, world_x, world_y, radius, strength)

    candidates = sorted(bucket_best.values(), key=lambda entry: entry[0])
    limited = candidates[:max_samples]

    samples: list[LavaLightSample] = []
    for _dist_sq, tile_x, tile_y, world_x, world_y, radius, strength in limited:
        samples.append(
            LavaLightSample(
                tile_x=tile_x,
                tile_y=tile_y,
                world_x=world_x,
                world_y=world_y,
                radius=radius,
                strength=strength,
            )
        )

    return samples
