"""Create-World-View fuer Pinecraft."""

import arcade
import arcade.gui

from settings import BACKGROUND_COLOR, WORLD_SEED


class CreateWorldView(arcade.View):
    """Untermenue zum Erstellen einer neuen Welt."""

    def __init__(self, host_lan: bool = False):
        super().__init__()
        self.host_lan = host_lan
        self.ui_manager = arcade.gui.UIManager()
        self.root = arcade.gui.UIAnchorLayout(size_hint=(1.0, 1.0))
        self.seed_input: arcade.gui.UIInputText | None = None
        self.name_input: arcade.gui.UIInputText | None = None
        self._built = False

    def on_show_view(self):
        arcade.set_background_color(BACKGROUND_COLOR)
        self.ui_manager.enable()
        if not self._built:
            self._build_ui()

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
            text="Host LAN World" if self.host_lan else "Create World",
            width=380,
            height=52,
            align="center",
            font_size=34,
            bold=True,
            text_color=arcade.color.WHITE,
            size_hint=None,
        )

        seed_label = arcade.gui.UILabel(
            text="Seed",
            width=380,
            height=20,
            align="left",
            font_size=14,
            text_color=arcade.color.WHITE,
            size_hint=None,
        )
        self.seed_input = arcade.gui.UIInputText(width=380, height=40, text=str(WORLD_SEED))

        world_name_label = arcade.gui.UILabel(
            text="World Name",
            width=380,
            height=20,
            align="left",
            font_size=14,
            text_color=arcade.color.WHITE,
            size_hint=None,
        )
        self.name_input = arcade.gui.UIInputText(width=380, height=40, text="MyWorld")

        self.port_input: arcade.gui.UIInputText | None = None
        if self.host_lan:
            port_label = arcade.gui.UILabel(
                text="Port",
                width=380,
                height=20,
                align="left",
                font_size=14,
                text_color=arcade.color.WHITE,
                size_hint=None,
            )
            self.port_input = arcade.gui.UIInputText(width=380, height=40, text="25565")

        start_button = arcade.gui.UIFlatButton(text="Start LAN Server" if self.host_lan else "Start World", width=380, height=42)
        back_button = arcade.gui.UIFlatButton(text="Back", width=380, height=36)

        start_button.on_click = self._on_start_world
        back_button.on_click = self._on_back

        container.add(title)
        container.add(arcade.gui.UIWidget(width=1, height=4))
        container.add(seed_label)
        container.add(self.seed_input)
        container.add(world_name_label)
        container.add(self.name_input)
        if self.port_input is not None:
            container.add(port_label)
            container.add(self.port_input)
        container.add(arcade.gui.UIWidget(width=1, height=8))
        container.add(start_button)
        container.add(back_button)

        self.root.add(container, anchor_x="center", anchor_y="center")
        self._built = True

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

    def _on_start_world(self, event):
        if self.window is None:
            return
        from game import GameView

        seed = self._parse_seed()
        world_name = self._read_world_name()
        if not self.host_lan:
            self.window.show_view(GameView(seed=seed, world_name=world_name))
            return

        try:
            port = int(self.port_input.text) if self.port_input is not None else 25565
            from network.server import LanServer

            server = LanServer(seed=seed, world_name=world_name, port=port)
            server.start()
            self.window.show_view(GameView(seed=seed, world_name=world_name, lan_server=server))
        except (OSError, ValueError):
            return

    def _on_back(self, event):
        if self.window is None:
            return
        from start_menu_view import StartMenuView

        self.window.show_view(StartMenuView())

    def on_key_press(self, symbol: int, modifiers: int):
        if symbol == arcade.key.ESCAPE:
            self._on_back(None)
        elif symbol == arcade.key.ENTER:
            self._on_start_world(None)
