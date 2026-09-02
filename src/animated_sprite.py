"""Basisklasse für animierte Sprites mit mehreren Animationszuständen."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

import arcade

from sprite_animation import SpriteAnimation


class AnimatedSprite(arcade.Sprite):
    """Ein Sprite, der verschiedene Animationen verwaltet.

    Beispiel:
        sprite = AnimatedSprite({
            "idle": ["assets/.../idle.png"],
            "walking": ["assets/.../walk01.png", "assets/.../walk02.png"],
        }, default_state="idle")
    """

    def __init__(
        self,
        animations: Mapping[str, Iterable[str | arcade.Texture] | SpriteAnimation] | None = None,
        fps: float = 12.0,
        default_state: str = "idle",
        facing_right: bool = True,
    ):
        super().__init__()
        self.facing_right = facing_right
        self.animations: dict[str, SpriteAnimation] = {}
        self.current_animation_state = default_state
        self.current_animation: SpriteAnimation | None = None

        if animations:
            self.load_animations(animations, fps=fps)

        if self.current_animation is None and self.animations:
            first_state = next(iter(self.animations))
            self.set_animation_state(first_state)

    def load_animations(
        self,
        animations: Mapping[str, Iterable[str | arcade.Texture] | SpriteAnimation],
        fps: float = 12.0,
    ):
        """Lädt mehrere Animationen aus einem Wörterbuch und baut SpriteAnimation-Objekte."""
        self.animations = {}

        for state_name, frame_data in animations.items():
            if isinstance(frame_data, SpriteAnimation):
                animation = frame_data
            else:
                animation = SpriteAnimation(frame_data, fps=fps)

            self.animations[state_name] = animation

        if self.current_animation_state not in self.animations and self.animations:
            self.current_animation_state = next(iter(self.animations))

        self.set_animation_state(self.current_animation_state)

    def set_animation_state(self, state_name: str):
        """Wechselt in einen neuen Animationszustand."""
        if state_name not in self.animations:
            return

        if self.current_animation_state == state_name:
            self.current_animation_state = state_name
            self.current_animation = self.animations[state_name]
            self.texture = self.current_animation.texture
            return

        self.current_animation_state = state_name
        self.current_animation = self.animations[state_name]
        self.current_animation.reset()
        self.texture = self.current_animation.texture

    def update_animation(self, delta_time: float, debug: bool = False):
        """Aktualisiert die aktuell ausgewählte Animation."""
        if self.current_animation is None:
            return

        self.current_animation.update(delta_time, debug=debug)
        self.texture = self.current_animation.texture

    def update(self, delta_time: float):
        """Standard-Update, das die aktive Animation weiterführt."""
        if self.facing_right:
            self.scale_x = abs(self.scale_x)
        else:
            self.scale_x = -(abs(self.scale_x))
            
        self.update_animation(delta_time)
