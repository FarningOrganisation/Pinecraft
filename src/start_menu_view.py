"""Startmenue-View fuer Pinecraft."""

import arcade
import arcade.gui

from settings import BACKGROUND_COLOR, START_FULLSCREEN


class StartMenuView(arcade.View):
    """Startmenue-Hub mit Navigation zu Create/Load-Untermenues."""

    def __init__(self):
        super().__init__()
        self.ui_manager = arcade.gui.UIManager()
        self.root = arcade.gui.UIAnchorLayout(size_hint=(1.0, 1.0))
        self._built = False
        self._fullscreen_enabled = START_FULLSCREEN
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

        self.fullscreen_button = arcade.gui.UIFlatButton(text="", width=360, height=36)
        create_world_button = arcade.gui.UIFlatButton(text="Create World", width=360, height=42)
        host_lan_button = arcade.gui.UIFlatButton(text="Host LAN World", width=360, height=42)
        join_lan_button = arcade.gui.UIFlatButton(text="Join LAN World", width=360, height=42)
        load_world_button = arcade.gui.UIFlatButton(text="Load World", width=360, height=42)
        quit_button = arcade.gui.UIFlatButton(text="Quit", width=360, height=36)

        self.fullscreen_button.on_click = self._on_toggle_fullscreen
        create_world_button.on_click = self._on_open_create_world
        host_lan_button.on_click = self._on_open_host_lan
        join_lan_button.on_click = self._on_open_join_lan
        load_world_button.on_click = self._on_open_load_world
        quit_button.on_click = self._on_quit

        container.add(title)
        container.add(subtitle)
        container.add(arcade.gui.UIWidget(width=1, height=4))
        container.add(arcade.gui.UIWidget(width=1, height=8))
        container.add(create_world_button)
        container.add(load_world_button)
        container.add(host_lan_button)
        container.add(join_lan_button)
        container.add(self.fullscreen_button)
        container.add(quit_button)

        self.root.add(container, anchor_x="center", anchor_y="center")

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
        self._sync_button_texts()

    def _on_open_create_world(self, event):
        if self.window is None:
            return
        from create_world_view import CreateWorldView

        self.window.show_view(CreateWorldView())

    def _on_open_host_lan(self, event):
        if self.window is None:
            return
        from load_world_view import LoadWorldView

        self.window.show_view(LoadWorldView(host_lan=True))

    def _on_open_join_lan(self, event):
        if self.window is None:
            return
        from join_lan_view import JoinLanView

        self.window.show_view(JoinLanView())

    def _on_open_load_world(self, event):
        if self.window is None:
            return
        from load_world_view import LoadWorldView

        self.window.show_view(LoadWorldView())

    def _on_quit(self, event):
        arcade.exit()

    def on_key_press(self, symbol: int, modifiers: int):
        if symbol == arcade.key.ENTER:
            self._on_open_create_world(None)
            return
        if symbol == arcade.key.F:
            self._on_toggle_fullscreen(None)
            return
