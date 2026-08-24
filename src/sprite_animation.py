"""Hilfsklassen für einzelne Sprite-Animationen.

Diese Datei enthält eine wiederverwendbare Animation, die von Arcade-Sprites
abgeleitet ist. Sie kann mit einer Liste von Texturen oder Bildpfaden
initialisiert werden und animiert diese mit einer festen FPS.
"""

from pathlib import Path
from typing import Iterable

import arcade


class SpriteAnimation(arcade.Sprite):
    """Eine einzelne Animation mit Bildfolgen.

    Beispiel:
        animation = SpriteAnimation([
            "assets/textures/characters/steve_walk01.png",
            "assets/textures/characters/steve_walk02.png",
        ], fps=8, loop=True)
    """

    def __init__(self, frames, fps: float = 12.0, loop: bool = True):
        super().__init__()

        self.frames = self._normalize_frames(frames)
        if not self.frames:
            raise ValueError("SpriteAnimation requires at least one frame.")

        self.fps = fps
        self.loop = loop
        self.frame_index = 0
        self.elapsed_time = 0.0
        self.has_finished = False
        self.texture = self.frames[0]

    def _normalize_frames(self, frames):
        """Normalisiert Frames zu Arcade-Texturen."""
        normalized = []

        for frame in frames:
            if isinstance(frame, arcade.Texture):
                normalized.append(frame)
            elif isinstance(frame, (str, Path)):
                normalized.append(arcade.load_texture(frame))
            else:
                raise TypeError(
                    "Frame muss ein Pfad, ein Path-Objekt oder eine Arcade-Texture sein."
                )

        return normalized

    def reset(self):
        """Setzt die Animation zurück zum ersten Bild."""
        self.frame_index = 0
        self.elapsed_time = 0.0
        self.has_finished = False
        self.texture = self.frames[0]

    def update(self, delta_time: float, debug: bool = False):
        """Aktualisiert die Animation anhand der FPS."""
        if self.has_finished:
            return

        if len(self.frames) <= 1:
            self.has_finished = not self.loop
            return

        frame_duration = 1.0 / self.fps
        self.elapsed_time += delta_time

        while self.elapsed_time >= frame_duration:
            self.elapsed_time -= frame_duration

            if self.loop:
                self.frame_index = (self.frame_index + 1) % len(self.frames)
                self.texture = self.frames[self.frame_index]
            elif self.frame_index < len(self.frames) - 1:
                self.frame_index += 1
                self.texture = self.frames[self.frame_index]
            else:
                self.elapsed_time = 0.0
                self.frame_index = len(self.frames) - 1
                self.texture = self.frames[self.frame_index]
                self.has_finished = True
                return
