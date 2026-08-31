"""Entwicklungs-Runner mit Auto-Restart bei Code-Aenderungen.

Hinweis: Das ist kein echtes In-Process-Hot-Reloading, sondern ein
sicherer Neustart des Spielprozesses bei Dateiaenderungen.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_WATCH_DIRS = [PROJECT_ROOT / "src", PROJECT_ROOT]
DEFAULT_EXTENSIONS = {".py"}
IGNORE_PARTS = {".git", ".venv", "__pycache__", "saves"}


def iter_watched_files(watch_dirs: Iterable[Path], extensions: set[str]) -> Iterable[Path]:
    """Liefert alle beobachteten Dateien rekursiv."""
    for base_dir in watch_dirs:
        if not base_dir.exists() or not base_dir.is_dir():
            continue

        for path in base_dir.rglob("*"):
            if not path.is_file():
                continue
            if any(part in IGNORE_PARTS for part in path.parts):
                continue
            if path.suffix.lower() not in extensions:
                continue
            yield path


def build_snapshot(watch_dirs: list[Path], extensions: set[str]) -> dict[str, int]:
    """Baut einen mtime-Snapshot der beobachteten Dateien."""
    snapshot: dict[str, int] = {}
    for path in iter_watched_files(watch_dirs, extensions):
        try:
            snapshot[str(path)] = path.stat().st_mtime_ns
        except FileNotFoundError:
            continue
    return snapshot


def snapshot_diff(old: dict[str, int], new: dict[str, int]) -> list[str]:
    """Ermittelt geaenderte, neue und geloeschte Dateien."""
    changed: list[str] = []

    old_keys = set(old.keys())
    new_keys = set(new.keys())

    for added in sorted(new_keys - old_keys):
        changed.append(f"+ {added}")

    for removed in sorted(old_keys - new_keys):
        changed.append(f"- {removed}")

    for key in sorted(old_keys & new_keys):
        if old[key] != new[key]:
            changed.append(f"~ {key}")

    return changed


def start_game_process() -> subprocess.Popen:
    """Startet main.py als Kindprozess."""
    cmd = [sys.executable, "main.py"]
    return subprocess.Popen(cmd, cwd=str(PROJECT_ROOT))


def stop_game_process(process: subprocess.Popen) -> None:
    """Beendet den Kindprozess kontrolliert."""
    if process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Auto-Restart fuer Pinecraft waehrend der Entwicklung")
    parser.add_argument("--interval", type=float, default=0.35, help="Polling-Intervall in Sekunden")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    watch_dirs = DEFAULT_WATCH_DIRS
    extensions = DEFAULT_EXTENSIONS

    print("[dev] Starte Pinecraft mit Auto-Restart...")
    print("[dev] Beobachte:")
    for d in watch_dirs:
        print(f"  - {d}")

    process = start_game_process()
    snapshot = build_snapshot(watch_dirs, extensions)

    def handle_shutdown(_sig, _frame):
        print("\n[dev] Beende Auto-Restart-Runner...")
        stop_game_process(process)
        raise SystemExit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    while True:
        time.sleep(max(0.05, float(args.interval)))

        new_snapshot = build_snapshot(watch_dirs, extensions)
        changed = snapshot_diff(snapshot, new_snapshot)

        # Wenn der Spielprozess von selbst endet, direkt neu starten.
        exited = process.poll() is not None
        if changed or exited:
            if changed:
                print("[dev] Aenderung erkannt, starte neu:")
                for item in changed[:8]:
                    print(f"    {item}")
                if len(changed) > 8:
                    print(f"    ... und {len(changed) - 8} weitere")
            elif exited:
                print("[dev] Spielprozess beendet, starte neu...")

            stop_game_process(process)
            process = start_game_process()
            snapshot = new_snapshot


if __name__ == "__main__":
    raise SystemExit(main())
