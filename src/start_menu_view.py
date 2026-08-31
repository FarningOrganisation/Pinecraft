"""Startmenue-View fuer Pinecraft."""

import arcade
import arcade.gui

from settings import BACKGROUND_COLOR, START_FULLSCREEN, WORLD_SEED


class StartMenuView(arcade.View):
    """Startmenue mit Seed, Weltname und Fullscreen-Umschalter."""

    def __init__(self):
        super().__init__()
        self.ui_manager = arcade.gui.UIManager()
        self.root = arcade.gui.UIAnchorLayout(size_hint=(1.0, 1.0))
        self._built = False
        self._fullscreen_enabled = START_FULLSCREEN
        self.seed_input: arcade.gui.UIInputText | None = None
        self.name_input: arcade.gui.UIInputText | None = None
        self.fullscreen_button: arcade.gui.UIFlatButton | None = None

    def on_show_view(self):
        arcade.set_background_color(BACKGROUND_COLOR)
        self.ui_manager.enable()
        if self.window is not None:
            self._fullscreen_enabled = bool(self.window.fullscreen)
        if not self._built:
            self._build_ui()
        else:
            self._sync_button_texts()

    def on_hide_view(self):
        self.ui_manager.disable()

    def on_draw(self):
        self.clear((22, 26, 34, 255))
        self.ui_manager.draw()

    def _build_ui(self):
        self.ui_manager.clear()
        self.ui_manager.add(self.root)

        container = arcade.gui.UIBoxLayout(vertical=True, space_between=12)

        title = arcade.gui.UILabel(
            text="Pinecraft",
            width=360,
            height=52,
            align="center",
            font_size=40,
            bold=True,
            text_color=arcade.color.WHITE,
            size_hint=None,
        )
        subtitle = arcade.gui.UILabel(
            text="Create or load a world",
            width=360,
            height=24,
            align="center",
            font_size=14,
            text_color=arcade.color.LIGHT_GRAY,
            size_hint=None,
        )

        seed_label = arcade.gui.UILabel(
            text="Seed",
            width=360,
            height=20,
            align="left",
            font_size=14,
            text_color=arcade.color.WHITE,
            size_hint=None,
        )
        self.seed_input = arcade.gui.UIInputText(width=360, height=40, text=str(WORLD_SEED))

        name_label = arcade.gui.UILabel(
            text="World Name",
            width=360,
            height=20,
            align="left",
            font_size=14,
            text_color=arcade.color.WHITE,
            size_hint=None,
        )
        self.name_input = arcade.gui.UIInputText(width=360, height=40, text="MyWorld")

        self.fullscreen_button = arcade.gui.UIFlatButton(text="", width=360, height=36)
        start_button = arcade.gui.UIFlatButton(text="Start World", width=360, height=42)
        quit_button = arcade.gui.UIFlatButton(text="Quit", width=360, height=36)

        self.fullscreen_button.on_click = self._on_toggle_fullscreen
        start_button.on_click = self._on_start_world
        quit_button.on_click = self._on_quit

        container.add(title)
        container.add(subtitle)
        container.add(arcade.gui.UIWidget(width=1, height=4))
        container.add(seed_label)
        container.add(self.seed_input)
        container.add(name_label)
        container.add(self.name_input)
        container.add(arcade.gui.UIWidget(width=1, height=8))
        container.add(self.fullscreen_button)
        container.add(start_button)
        container.add(quit_button)

        self.root.add(container, anchor_x="center", anchor_y="center")

        self._built = True
        self._sync_button_texts()

    def _sync_button_texts(self):
        if self.fullscreen_button is not None:
            state = "ON" if self._fullscreen_enabled else "OFF"
            self.fullscreen_button.text = f"Fullscreen: {state}"
            self.fullscreen_button.trigger_full_render()

    def _parse_seed(self) -> int:
        if self.seed_input is None:
            return WORLD_SEED
        text = (self.seed_input.text or "").strip()
        if not text:
            return WORLD_SEED
        try:
            return int(text)
        except ValueError:
            return WORLD_SEED

    def _read_world_name(self) -> str:
        if self.name_input is None:
            return "World"
        text = (self.name_input.text or "").strip()
        return text if text else "World"

    def _on_toggle_fullscreen(self, event):
        self._fullscreen_enabled = not self._fullscreen_enabled
        if self.window is not None:
            self.window.set_fullscreen(self._fullscreen_enabled)
        self._sync_button_texts()

    def _on_start_world(self, event):
        if self.window is None:
            return

        from game import GameView

        seed = self._parse_seed()
        world_name = self._read_world_name()
        self.window.set_fullscreen(self._fullscreen_enabled)
        self.window.show_view(GameView(seed=seed, world_name=world_name))

    def _on_quit(self, event):
        arcade.exit()

    def on_key_press(self, symbol: int, modifiers: int):
        if symbol == arcade.key.ENTER:
            self._on_start_world(None)
            return
        if symbol == arcade.key.F:
            self._on_toggle_fullscreen(None)
            return
