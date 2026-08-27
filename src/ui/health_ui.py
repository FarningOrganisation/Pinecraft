"""Health HUD rendering for the player."""

import arcade

from paths import textures_dir
from resource_manager import resource_manager


class HealthUI:
    """Zeichnet die Herzen links oberhalb der Hotbar."""

    def __init__(self, player):
        self.player = player
        ui_texture_dir = textures_dir("ui")
        self.heart_full_texture = resource_manager.load_texture(ui_texture_dir / "heart_full.png")
        self.heart_empty_texture = resource_manager.load_texture(ui_texture_dir / "heart_empty.png")
        self.heart_size = 16
        self.heart_gap = 2

    def get_bar_origin(self, hotbar) -> tuple[float, float]:
        """Liefert die linke untere Startposition der Herzreihe."""
        start_x = hotbar.slot_x_start
        start_y = hotbar.slot_y + hotbar.slot_size + 16
        return start_x, start_y

    def draw(self, hotbar):
        """Zeichnet die Lebenspunkte als Herzreihe."""
        heart_count = max(0, int(getattr(self.player, "max_health", 0)))
        if heart_count <= 0:
            return

        start_x, start_y = self.get_bar_origin(hotbar)
        current_health = max(0, int(getattr(self.player, "health", 0)))

        for index in range(heart_count):
            texture = self.heart_full_texture if index < current_health else self.heart_empty_texture
            rect = arcade.rect.XYWH(
                start_x + index * (self.heart_size + self.heart_gap) + self.heart_size / 2,
                start_y + self.heart_size / 2,
                self.heart_size,
                self.heart_size,
            )
            arcade.draw_texture_rect(texture, rect, alpha=255)
