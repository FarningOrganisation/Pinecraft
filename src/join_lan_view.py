"""Ansicht zum Beitreten einer lokalen Pinecraft-Mehrspielersitzung."""

from __future__ import annotations

import arcade
import arcade.gui

from settings import BACKGROUND_COLOR


class JoinLanView(arcade.View):
    """Fragt Anzeigename, IP-Adresse und Port eines LAN-Hosts ab."""

    def __init__(self):
        super().__init__()
        self.ui_manager = arcade.gui.UIManager()
        self.root = arcade.gui.UIAnchorLayout(size_hint=(1.0, 1.0))
        self.name_input: arcade.gui.UIInputText | None = None
        self.host_input: arcade.gui.UIInputText | None = None
        self.port_input: arcade.gui.UIInputText | None = None
        self.status_label: arcade.gui.UILabel | None = None

    def on_show_view(self):
        arcade.set_background_color(BACKGROUND_COLOR)
        self.ui_manager.enable()
        if self.status_label is None:
            self._build_ui()

    def on_hide_view(self):
        self.ui_manager.disable()

    def on_draw(self):
        self.clear((22, 26, 34, 255))
        self.ui_manager.draw()

    def _build_ui(self) -> None:
        self.ui_manager.add(self.root)
        container = arcade.gui.UIBoxLayout(vertical=True, space_between=10)
        title = arcade.gui.UILabel(text="Join LAN World", width=380, height=48, align="center", font_size=32, bold=True, text_color=arcade.color.WHITE)
        self.name_input = arcade.gui.UIInputText(width=380, height=40, text="Player")
        self.host_input = arcade.gui.UIInputText(width=380, height=40, text="127.0.0.1")
        self.port_input = arcade.gui.UIInputText(width=380, height=40, text="25565")
        self.status_label = arcade.gui.UILabel(text="", width=380, height=24, align="center", font_size=13, text_color=arcade.color.LIGHT_GRAY)
        join_button = arcade.gui.UIFlatButton(text="Join", width=380, height=42)
        back_button = arcade.gui.UIFlatButton(text="Back", width=380, height=36)
        join_button.on_click = self._on_join
        back_button.on_click = self._on_back
        container.add(title)
        for label, field in (("Player Name", self.name_input), ("Host IP", self.host_input), ("Port", self.port_input)):
            container.add(arcade.gui.UILabel(text=label, width=380, height=20, align="left", font_size=14, text_color=arcade.color.WHITE))
            container.add(field)
        container.add(self.status_label)
        container.add(join_button)
        container.add(back_button)
        self.root.add(container, anchor_x="center", anchor_y="center")

    def _on_join(self, event) -> None:
        if self.window is None or self.name_input is None or self.host_input is None or self.port_input is None:
            return
        try:
            from game import GameView
            from network.client import LanClient

            client = LanClient.connect(self.host_input.text.strip(), int(self.port_input.text), self.name_input.text.strip())
            self.window.show_view(
                GameView(
                    seed=client.seed,
                    world_name=client.world_name,
                    save_data=client.initial_save_data,
                    lan_client=client,
                )
            )
        except (ConnectionError, OSError, ValueError) as exc:
            assert self.status_label is not None
            self.status_label.text = f"Connection failed: {exc}"
            self.status_label.trigger_full_render()

    def _on_back(self, event) -> None:
        if self.window is not None:
            from start_menu_view import StartMenuView

            self.window.show_view(StartMenuView())