"""Zentrale Projektpfade fuer robuste Datei-Zugriffe."""

from pathlib import Path


SRC_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DIR.parent
ASSETS_DIR = PROJECT_ROOT / "assets"


def textures_dir(*parts: str) -> Path:
    """Liefert den Texture-Ordner oder einen Unterpfad davon."""
    return ASSETS_DIR / "textures" / Path(*parts)
