"""Global asset cache for textures and sounds."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import arcade

from paths import ASSETS_DIR


class ResourceManager:
    """Caches assets by path so they are loaded only once."""

    def __init__(self):
        self._texture_cache: dict[str, arcade.Texture] = {}
        self._sound_cache: dict[str, arcade.Sound] = {}

    def _normalize_path(self, path: str | Path) -> Path:
        path_obj = Path(path)
        if not path_obj.is_absolute():
            path_obj = (ASSETS_DIR / path_obj).resolve()
        return path_obj

    def _cache_key(self, path: str | Path) -> str:
        return str(self._normalize_path(path))

    def load_texture_in_textures(self, relative_path: str | Path) -> arcade.Texture:
        """Load a texture from the assets/textures directory and cache it by path."""
        target = self._normalize_path(Path("textures") / relative_path)
        key = str(target)
        if key not in self._texture_cache:
            self._texture_cache[key] = arcade.load_texture(target)
        return self._texture_cache[key]

    def load_sound_in_sounds(self, relative_path: str | Path) -> arcade.Sound:
        """Load a sound from the assets/sounds directory and cache it by path."""
        target = self._normalize_path(Path("sounds") / relative_path)
        key = str(target)
        if key not in self._sound_cache:
            self._sound_cache[key] = arcade.Sound(target)
        return self._sound_cache[key]

    def load_texture(self, path: str | Path) -> arcade.Texture:
        """Load a texture from an arbitrary path and cache it by normalized path."""
        key = self._cache_key(path)
        if key not in self._texture_cache:
            self._texture_cache[key] = arcade.load_texture(path)
        return self._texture_cache[key]

    def load_sound(self, path: str | Path) -> arcade.Sound:
        """Load a sound from an arbitrary path and cache it by normalized path."""
        key = self._cache_key(path)
        if key not in self._sound_cache:
            self._sound_cache[key] = arcade.Sound(path)
        return self._sound_cache[key]


resource_manager = ResourceManager()
