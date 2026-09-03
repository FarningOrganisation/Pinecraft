"""Bubble HUD rendering for underwater breathing."""

import time

import arcade
import arcade.gui

from paths import textures_dir
from resource_manager import resource_manager


class BubbleUI(arcade.gui.UIWidget):
    """Draws air bubbles above the health HUD while the player is underwater."""

    POP_VISIBLE_SECONDS = 0.5

    def __init__(self, player, hotbar, health_ui):
        super().__init__(width=1, height=1, size_hint=None)
        self.player = player
        self.hotbar = hotbar
        self.health_ui = health_ui
        ui_texture_dir = textures_dir("ui")
        self.bubble_full_texture = resource_manager.load_texture(ui_texture_dir / "bubble1.png")
        self.bubble_pop_texture = resource_manager.load_texture(ui_texture_dir / "bubble2.png")
        self.bubble_size = 14
        self.bubble_gap = 2
        self._last_remaining: int | None = None
        self._pop_visible_until: dict[int, float] = {}

    def _bubble_row_geometry(self) -> tuple[float, float, float, float, int]:
        """Liefert (x, y, width, height, bubble_count) der Bubble-Leiste."""
        bubble_count = max(0, int(self.player.max_air_bubbles))
        row_width = 0 if bubble_count <= 0 else bubble_count * self.bubble_size + (bubble_count - 1) * self.bubble_gap
        row_height = self.bubble_size
        start_x, hearts_y = self.health_ui.get_bar_origin()
        start_y = hearts_y + self.health_ui.heart_size + 8
        return start_x, start_y, row_width, row_height, bubble_count

    def _sync_widget_rect(self) -> int:
        """Synchronisiert Widget-Groesse und -Position mit der Bubble-Leiste."""
        start_x, start_y, row_width, row_height, bubble_count = self._bubble_row_geometry()
        width = max(1, int(row_width))
        height = max(1, int(row_height))
        self.width = width
        self.height = height
        self.rect = arcade.rect.XYWH(
            start_x + row_width / 2,
            start_y + row_height / 2,
            row_width,
            row_height,
        )
        return bubble_count

    def _update_pop_state(self, remaining: int, bubble_count: int, now: float) -> None:
        """Aktualisiert, welche Blasen als Pop-Frame sichtbar sein sollen."""
        if self._last_remaining is None:
            self._last_remaining = remaining
            return

        previous = max(0, min(self._last_remaining, bubble_count))
        current = max(0, min(remaining, bubble_count))

        if current < previous:
            for index in range(current, previous):
                self._pop_visible_until[index] = now + self.POP_VISIBLE_SECONDS
        elif current > previous:
            for index in range(previous, current):
                self._pop_visible_until.pop(index, None)

        for index in list(self._pop_visible_until.keys()):
            if index >= bubble_count or self._pop_visible_until[index] <= now:
                self._pop_visible_until.pop(index, None)

        self._last_remaining = current

    def draw(self):
        """Draws the bubble row only while the player is inside water."""
        if not self.player.in_water:
            self._last_remaining = None
            self._pop_visible_until.clear()
            return

        bubble_count = max(0, int(self.player.max_air_bubbles))
        if bubble_count <= 0:
            return

        remaining = max(0, int(self.player.air_bubbles))
        now = time.monotonic()
        self._update_pop_state(remaining, bubble_count, now)

        for index in range(bubble_count):
            if index < remaining:
                texture = self.bubble_full_texture
            elif self._pop_visible_until.get(index, 0.0) > now:
                texture = self.bubble_pop_texture
            else:
                continue

            rect = arcade.rect.XYWH(
                index * (self.bubble_size + self.bubble_gap) + self.bubble_size / 2,
                self.bubble_size / 2,
                self.bubble_size,
                self.bubble_size,
            )
            arcade.draw_texture_rect(texture, rect, alpha=255, pixelated=True)

    def do_render(self, surface):
        self._sync_widget_rect()
        # Wichtig für dynamische Blasenanzahl: alte Pixelreste entfernen.
        surface.clear((0, 0, 0, 0))
        self.draw()
