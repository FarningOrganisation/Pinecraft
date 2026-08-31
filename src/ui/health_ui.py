"""Health HUD rendering for the player."""

import arcade
import arcade.gui

from paths import textures_dir
from resource_manager import resource_manager


class HealthUI(arcade.gui.UIWidget):
    """Zeichnet die Herzen links oberhalb der Hotbar."""

    def __init__(self, player, hotbar):
        super().__init__()
        self.player = player
        self.hotbar = hotbar
        ui_texture_dir = textures_dir("ui")
        self.heart_full_texture = resource_manager.load_texture(ui_texture_dir / "heart_full.png")
        self.heart_empty_texture = resource_manager.load_texture(ui_texture_dir / "heart_empty.png")
        self.heart_size = 16
        self.heart_gap = 2
        self.size_hint = (1.0, 1.0)

    def get_bar_origin(self) -> tuple[float, float]:
        """Liefert die linke untere Startposition der Herzreihe."""
        start_x = self.hotbar.slot_x_start
        start_y = self.hotbar.slot_y + self.hotbar.slot_size + 16
        return start_x, start_y

    def draw(self):
        """Zeichnet die Lebenspunkte als Herzreihe."""
        heart_count = max(0, int(getattr(self.player, "max_health", 0)))
        if heart_count <= 0:
            return

        start_x, start_y = self.get_bar_origin()
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

    def do_render(self, surface):
        self.draw()
