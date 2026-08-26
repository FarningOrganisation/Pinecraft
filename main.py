"""Startskript fuer Pinecraft.

Ermoeglicht den Start mit `python main.py`, auch wenn der eigentliche Code in `src/` liegt.
"""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from game import main as run_game  # noqa: E402


if __name__ == "__main__":
    run_game()
