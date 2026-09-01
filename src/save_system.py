"""Speichern und Laden von Spielstaenden fuer Pinecraft."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

from inventory import InventorySlot

SAVE_VERSION = 1
SAVE_FILE_SUFFIX = ".json"


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def saves_dir() -> Path:
    path = _project_root() / "saves"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sanitize_world_name(name: str) -> str:
    raw = (name or "World").strip()
    if not raw:
        raw = "World"
    cleaned = "".join(ch for ch in raw if ch.isalnum() or ch in ("-", "_", " "))
    cleaned = "_".join(cleaned.split())
    return cleaned or "World"


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_inventory_slots(slots: list[InventorySlot]) -> list[dict[str, int | None]]:
    payload: list[dict[str, int | None]] = []
    for slot in slots:
        item = slot.item if isinstance(slot.item, int) else None
        count = int(slot.count) if slot.count > 0 else 0
        payload.append({"item": item, "count": count})
    return payload


def _serialize_chunk_blocks(world) -> dict[str, list[list[int]]]:
    blocks_by_chunk: dict[int, list[list[int]]] = {}
    for chunk_x, blocks in world.saved_chunk_blocks.items():
        blocks_by_chunk[int(chunk_x)] = [row[:] for row in blocks]
    for chunk_x, chunk in world.chunks.items():
        blocks_by_chunk[int(chunk_x)] = [row[:] for row in chunk.blocks]

    return {str(chunk_x): blocks for chunk_x, blocks in sorted(blocks_by_chunk.items())}


def _serialize_chunk_liquid(world, attr_name: str) -> dict[str, list[list[float]]]:
    liquid_by_chunk: dict[int, dict[tuple[int, int], float]] = {}
    saved_attr = f"saved_chunk_{attr_name}"

    for chunk_x, values in getattr(world, saved_attr).items():
        liquid_by_chunk[int(chunk_x)] = dict(values)

    for chunk_x, chunk in world.chunks.items():
        liquid_by_chunk[int(chunk_x)] = dict(getattr(chunk, attr_name))

    payload: dict[str, list[list[float]]] = {}
    for chunk_x, values in sorted(liquid_by_chunk.items()):
        cells: list[list[float]] = []
        for (local_x, y), amount in sorted(values.items(), key=lambda entry: (entry[0][1], entry[0][0])):
            if amount <= 0.0:
                continue
            cells.append([int(local_x), int(y), float(amount)])
        if cells:
            payload[str(chunk_x)] = cells
    return payload


def build_save_payload(game_view, runtime_state: dict | None = None) -> dict:
    world = game_view.world
    player = game_view.player
    inventory = player.inventory

    placed_items: list[list[int]] = []
    for (world_x, y), item_id in sorted(world.placed_items.items(), key=lambda entry: (entry[0][1], entry[0][0])):
        placed_items.append([int(world_x), int(y), int(item_id)])

    payload = {
        "meta": {
            "save_version": SAVE_VERSION,
            "saved_at_utc": _now_iso_utc(),
            "world_name": game_view.world_name,
        },
        "world": {
            "seed": int(world.seed),
            "spawn_point": {
                "x": float(world.spawn_x if world.spawn_x is not None else player.center_x),
                "y": float(world.spawn_y if world.spawn_y is not None else player.center_y),
            },
            "changed_blocks": _serialize_chunk_blocks(world),
            "changed_water": _serialize_chunk_liquid(world, "water"),
            "changed_lava": _serialize_chunk_liquid(world, "lava"),
            "items": placed_items,
        },
        "player": {
            "position": {"x": float(player.center_x), "y": float(player.center_y)},
            "velocity": {"x": float(player.change_x), "y": float(player.change_y)},
            "health": int(player.health),
            "max_health": int(player.max_health),
            "air_bubbles": int(player.air_bubbles),
            "max_air_bubbles": int(player.max_air_bubbles),
            "selected_hotbar_slot": int(player.selected_hotbar_slot),
            "facing_right": bool(getattr(player, "facing_right", True)),
        },
        "inventory": {
            "slots": _serialize_inventory_slots(inventory.slots),
        },
        "state": {
            "time_of_day": float(game_view.time_of_day),
        },
    }

    if runtime_state:
        state = payload.get("state")
        if isinstance(state, dict):
            state.update(runtime_state)

    return payload


def save_game(game_view, save_name: str | None = None, runtime_state: dict | None = None) -> Path:
    payload = build_save_payload(game_view, runtime_state=runtime_state)
    base_name = _sanitize_world_name(save_name or game_view.world_name)
    target = saves_dir() / f"{base_name}{SAVE_FILE_SUFFIX}"

    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    return target


def load_save(save_path: str | Path) -> dict:
    path = Path(save_path)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError("Save-Datei hat ein ungueltiges Format.")

    save_version = payload.get("meta", {}).get("save_version")
    if save_version != SAVE_VERSION:
        raise ValueError(f"Save-Version {save_version} wird nicht unterstuetzt.")

    return payload


def list_saves() -> list[dict[str, str | int]]:
    entries: list[dict[str, str | int]] = []
    for path in sorted(saves_dir().glob(f"*{SAVE_FILE_SUFFIX}"), key=lambda p: p.stat().st_mtime, reverse=True):
        world_name = path.stem
        seed = "?"
        saved_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()

        try:
            payload = load_save(path)
            meta = payload.get("meta", {})
            world = payload.get("world", {})
            world_name = str(meta.get("world_name") or world_name)
            seed = int(world.get("seed")) if world.get("seed") is not None else "?"
            saved_at = str(meta.get("saved_at_utc") or saved_at)
        except Exception:
            pass

        entries.append(
            {
                "file_name": path.name,
                "path": str(path),
                "world_name": world_name,
                "seed": seed,
                "saved_at_utc": saved_at,
            }
        )

    return entries


def delete_save(file_name: str) -> Path:
    """Loescht eine Save-Datei im Saves-Ordner und liefert den geloeschten Pfad."""
    if not file_name or not file_name.endswith(SAVE_FILE_SUFFIX):
        raise ValueError("Ungueltiger Save-Dateiname")

    base_name = Path(file_name).name
    if base_name != file_name:
        raise ValueError("Pfadangaben sind nicht erlaubt")

    target = saves_dir() / base_name
    if not target.exists():
        raise FileNotFoundError("Save-Datei nicht gefunden")

    target.unlink()
    return target


def build_world_from_save_data(save_data: dict) -> dict:
    """Normalisiert Save-Daten fuer die Wiederherstellung im GameView."""
    data = deepcopy(save_data)
    return data
