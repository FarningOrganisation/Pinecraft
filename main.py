"""Startskript fuer Pinecraft.

Ermoeglicht den Start mit `python main.py`, auch wenn der eigentliche Code in `src/` liegt.
"""

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from game import main as run_game  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pinecraft Launcher")
    parser.add_argument("--load-save", type=str, default=None, help="Lade direkt eine Save-Datei")
    parser.add_argument(
        "--dev-autosave-name",
        type=str,
        default=None,
        help="Aktiviere Auto-Save beim Beenden (Save-Name ohne Dateiendung)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_game(load_save_path=args.load_save, dev_autosave_name=args.dev_autosave_name)
