"""Ingame-Menue-View fuer Pinecraft."""

import arcade
import arcade.gui

from settings import START_FULLSCREEN
from start_menu_view import StartMenuView


class GameMenuView(arcade.View):
    """Ingame-Menue mit Fullscreen-Umschalter und Rueckweg ins Startmenue."""

    def __init__(self, game_view):
        super().__init__()
        self.game_view = game_view
        self.ui_manager = arcade.gui.UIManager()
        self.root = arcade.gui.UIAnchorLayout(size_hint=(1.0, 1.0))
        self._built = False
        self._fullscreen_enabled = START_FULLSCREEN
        self.fullscreen_button: arcade.gui.UIFlatButton | None = None
        self._card_width = 320
        self._card_height = 210

    def on_show_view(self):
        self.ui_manager.enable()
        if self.window is not None:
            self._fullscreen_enabled = bool(self.window.fullscreen)
        if not self._built:
            self._build_ui()
        else:
            self._sync_button_texts()

    def on_hide_view(self):
        self.ui_manager.disable()

    def _build_ui(self):
        self.ui_manager.clear()
        self.ui_manager.add(self.root)

        card = arcade.gui.UIBoxLayout(vertical=True, space_between=12)
        title = arcade.gui.UILabel(
            text="Game Menu",
            width=self._card_width,
            height=42,
            align="center",
            font_size=28,
            bold=True,
            text_color=arcade.color.WHITE,
            size_hint=None,
        )
        self.fullscreen_button = arcade.gui.UIFlatButton(text="", width=self._card_width, height=36)
        resume_button = arcade.gui.UIFlatButton(text="Resume", width=self._card_width, height=40)
        start_menu_button = arcade.gui.UIFlatButton(text="Back To Start Menu", width=self._card_width, height=40)

        self.fullscreen_button.on_click = self._on_toggle_fullscreen
        resume_button.on_click = self._on_resume
        start_menu_button.on_click = self._on_back_to_start

        card.add(title)
        card.add(self.fullscreen_button)
        card.add(resume_button)
        card.add(start_menu_button)

        self.root.add(card, anchor_x="center", anchor_y="center")

        self._built = True
        self._sync_button_texts()

    def _sync_button_texts(self):
        if self.fullscreen_button is not None:
            state = "ON" if self._fullscreen_enabled else "OFF"
            self.fullscreen_button.text = f"Fullscreen: {state}"
            self.fullscreen_button.trigger_full_render()

    def _on_toggle_fullscreen(self, event):
        self._fullscreen_enabled = not self._fullscreen_enabled
        if self.window is not None:
            self.window.set_fullscreen(self._fullscreen_enabled)
            self.on_resize(int(self.window.width), int(self.window.height))
            # GameView kann im Hintergrund liegen und bekommt das Resize-Event sonst zu spaet.
            if self.game_view is not None:
                self.game_view.on_resize(int(self.window.width), int(self.window.height))
        self._sync_button_texts()

    def _on_resume(self, event):
        if self.window is not None:
            self.window.show_view(self.game_view)

    def _on_back_to_start(self, event):
        if self.window is None:
            return
        self.window.show_view(StartMenuView())

    def on_draw(self):
        if self.game_view is not None:
            self.game_view.on_draw()
        else:
            self.clear((0, 0, 0, 255))

        if self.window is not None:
            # Sicherstellen, dass Overlay und UI immer in Fensterkoordinaten gezeichnet werden.
            self.window.default_camera.use()
            cx = self.window.width * 0.5
            cy = self.window.height * 0.5
            # Nur die Menuekarte abdunkeln, nicht den ganzen Bildschirm.
            arcade.draw_rect_filled(
                arcade.rect.XYWH(cx, cy, self._card_width + 56, self._card_height + 70),
                (10, 14, 22, 145),
            )
            arcade.draw_rect_outline(
                arcade.rect.XYWH(cx, cy, self._card_width + 56, self._card_height + 70),
                (255, 255, 255, 70),
                2,
            )

        self.ui_manager.draw()

    def on_resize(self, width: int, height: int):
        """Synchronisiert die Menue-UI nach Fenster-/Fullscreen-Aenderungen."""
        super().on_resize(width, height)
        if self.fullscreen_button is not None:
            self.fullscreen_button.trigger_full_render()

    def on_key_press(self, symbol: int, modifiers: int):
        if symbol == arcade.key.ESCAPE and self.window is not None:
            self.window.show_view(self.game_view)
            return
