"""Bubble HUD rendering for underwater breathing."""

import arcade

from paths import textures_dir
from resource_manager import resource_manager


class BubbleUI:
    """Draws air bubbles above the health HUD while the player is underwater."""

    def __init__(self, player):
        self.player = player
        ui_texture_dir = textures_dir("ui")
        self.bubble_full_texture = resource_manager.load_texture(ui_texture_dir / "bubble1.png")
        self.bubble_pop_texture = resource_manager.load_texture(ui_texture_dir / "bubble2.png")
        self.bubble_size = 14
        self.bubble_gap = 2

    def draw(self, hotbar, health_ui):
        """Draws the bubble row only while the player is inside water."""
        if not bool(getattr(self.player, "in_water", False)):
            return

        bubble_count = max(0, int(getattr(self.player, "max_air_bubbles", 0)))
        if bubble_count <= 0:
            return

        start_x, hearts_y = health_ui.get_bar_origin(hotbar)
        start_y = hearts_y + health_ui.heart_size + 8
        remaining = max(0, int(getattr(self.player, "air_bubbles", 0)))

        for index in range(bubble_count):
            texture = self.bubble_full_texture if index < remaining else self.bubble_pop_texture
            rect = arcade.rect.XYWH(
                start_x + index * (self.bubble_size + self.bubble_gap) + self.bubble_size / 2,
                start_y + self.bubble_size / 2,
                self.bubble_size,
                self.bubble_size,
            )
            arcade.draw_texture_rect(texture, rect, alpha=255)
