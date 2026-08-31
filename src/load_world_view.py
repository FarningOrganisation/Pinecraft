"""Load-World-View fuer Pinecraft."""

from dataclasses import replace
from datetime import datetime

import arcade
import arcade.gui
from arcade.gui.experimental import UIScrollArea
from arcade.gui.experimental.scroll_area import UIScrollBar

from save_system import delete_save, list_saves, load_save
from settings import BACKGROUND_COLOR


class LoadWorldView(arcade.View):
    """Untermenue zum Laden vorhandener Spielstaende."""

    def __init__(self):
        super().__init__()
        self.ui_manager = arcade.gui.UIManager()
        self.root = arcade.gui.UIAnchorLayout(size_hint=(1.0, 1.0))
        self.status_label: arcade.gui.UILabel | None = None
        self._status_text = ""
        self._save_entries: list[dict[str, str | int]] = []
        self._selected_file_name: str | None = None
        self._entry_buttons: dict[str, arcade.gui.UIFlatButton] = {}
        self._entry_button_style_template: dict[str, object] | None = None

    def on_show_view(self):
        arcade.set_background_color(BACKGROUND_COLOR)
        self.ui_manager.enable()
        self._build_ui()

    def on_hide_view(self):
        self.ui_manager.disable()

    def on_draw(self):
        self.clear((22, 26, 34, 255))
        self.ui_manager.draw()

    def _build_ui(self):
        self.ui_manager.clear()
        self.root = arcade.gui.UIAnchorLayout(size_hint=(1.0, 1.0))
        self.ui_manager.add(self.root)

        panel_width = 560
        list_width = 520
        row_height = 36
        row_gap = 6
        list_viewport_height = 260

        container = arcade.gui.UIBoxLayout(vertical=True, space_between=10)

        title = arcade.gui.UILabel(
            text="Load World",
            width=panel_width,
            height=50,
            align="center",
            font_size=34,
            bold=True,
            text_color=arcade.color.WHITE,
            size_hint=None,
        )
        container.add(title)
        container.add(arcade.gui.UIWidget(width=1, height=8))

        self._save_entries = sorted(
            list_saves(),
            key=lambda entry: self._parse_saved_at(entry.get("saved_at_utc")),
            reverse=True,
        )
        self._entry_buttons.clear()

        if not self._save_entries:
            empty = arcade.gui.UILabel(
                text="No save files found",
                width=panel_width,
                height=24,
                align="center",
                font_size=14,
                text_color=arcade.color.LIGHT_GRAY,
                size_hint=None,
            )
            container.add(empty)
        else:
            content_height = max(
                list_viewport_height,
                len(self._save_entries) * (row_height + row_gap) - row_gap,
            )
            entry_list = arcade.gui.UIBoxLayout(
                vertical=True,
                space_between=row_gap,
                size_hint=None,
                width=list_width,
                height=content_height,
            )
            for entry in self._save_entries:
                world_name = str(entry.get("world_name", "World"))
                seed = entry.get("seed", "?")
                file_name = str(entry.get("file_name", ""))
                row_button = arcade.gui.UIFlatButton(
                    text=f"{world_name} (seed {seed})",
                    width=list_width,
                    height=row_height,
                    style=self._new_entry_button_style(),
                )
                row_button.on_click = self._make_select_handler(file_name)
                self._entry_buttons[file_name] = row_button
                entry_list.add(row_button)

            scroll_row = arcade.gui.UIBoxLayout(
                vertical=False,
                size_hint=None,
                width=panel_width,
                height=list_viewport_height,
                space_between=8,
            )
            scroll_area = scroll_row.add(
                UIScrollArea(
                    width=list_width + 10,
                    height=list_viewport_height,
                    size_hint=None,
                )
            )
            scroll_area.with_border(color=arcade.color.LIGHT_GRAY)
            scroll_area.add(entry_list)
            scroll_row.add(UIScrollBar(scroll_area))
            container.add(scroll_row)

        self._refresh_entry_labels()

        self.status_label = arcade.gui.UILabel(
            text=self._status_text,
            width=panel_width,
            height=22,
            align="center",
            font_size=13,
            text_color=arcade.color.LIGHT_GRAY,
            size_hint=None,
        )

        action_row = arcade.gui.UIBoxLayout(vertical=False, size_hint=None, width=panel_width, height=40, space_between=12)
        load_button = arcade.gui.UIFlatButton(text="Load", width=274, height=40)
        delete_button = arcade.gui.UIFlatButton(text="Delete", width=274, height=40)
        load_button.on_click = self._on_load_selected
        delete_button.on_click = self._on_delete_selected
        action_row.add(load_button)
        action_row.add(delete_button)
        back_button = arcade.gui.UIFlatButton(text="Back", width=panel_width, height=34)
        back_button.on_click = self._on_back

        container.add(arcade.gui.UIWidget(width=1, height=10))
        container.add(self.status_label)
        container.add(action_row)
        container.add(back_button)

        self.root.add(container, anchor_x="center", anchor_y="center")

    def _make_select_handler(self, file_name: str):
        def _handle(event):
            self._on_select_world(file_name)

        return _handle

    def _entry_display_text(self, entry: dict[str, str | int], selected: bool) -> str:
        world_name = str(entry.get("world_name", "World"))
        seed = entry.get("seed", "?")
        return f"{world_name} (seed {seed})"

    @staticmethod
    def _parse_saved_at(raw_saved_at) -> float:
        if not raw_saved_at:
            return 0.0
        try:
            return datetime.fromisoformat(str(raw_saved_at)).timestamp()
        except ValueError:
            return 0.0

    def _new_entry_button_style(self) -> dict[str, object]:
        if self._entry_button_style_template is None:
            probe = arcade.gui.UIFlatButton(text="", width=1, height=1)
            self._entry_button_style_template = {key: replace(value) for key, value in probe.style.items()}

        return {key: replace(value) for key, value in self._entry_button_style_template.items()}

    @staticmethod
    def _apply_entry_button_style(button: arcade.gui.UIFlatButton, selected: bool) -> None:
        if selected:
            normal_bg = (24, 30, 42, 255)
            hover_bg = (34, 42, 58, 255)
            press_bg = (46, 56, 76, 255)
            font_color = (255, 255, 255, 255)
        else:
            normal_bg = (44, 62, 80, 255)
            hover_bg = (58, 80, 102, 255)
            press_bg = (70, 96, 120, 255)
            font_color = (235, 241, 247, 255)

        button.style["normal"].bg = normal_bg
        button.style["hover"].bg = hover_bg
        button.style["press"].bg = press_bg
        button.style["disabled"].bg = normal_bg
        button.style["normal"].font_color = font_color
        button.style["hover"].font_color = font_color
        button.style["press"].font_color = font_color
        button.style["disabled"].font_color = font_color

    def _refresh_entry_labels(self):
        existing_names = {str(entry.get("file_name", "")) for entry in self._save_entries}
        if self._selected_file_name not in existing_names:
            self._selected_file_name = None

        for entry in self._save_entries:
            file_name = str(entry.get("file_name", ""))
            button = self._entry_buttons.get(file_name)
            if button is None:
                continue
            is_selected = file_name == self._selected_file_name
            button.text = self._entry_display_text(entry, selected=is_selected)
            self._apply_entry_button_style(button, selected=is_selected)
            button.trigger_full_render()

    def _on_select_world(self, file_name: str):
        self._selected_file_name = file_name
        self._status_text = f"Selected: {file_name}"
        if self.status_label is not None:
            self.status_label.text = self._status_text
            self.status_label.trigger_full_render()
        self._refresh_entry_labels()

    def _on_load(self, file_name: str):
        if self.window is None:
            return

        from game import GameView

        try:
            entries = {entry["file_name"]: entry for entry in list_saves()}
            entry = entries.get(file_name)
            if entry is None:
                raise FileNotFoundError("Save file not found")

            save_data = load_save(entry["path"])
            world_data = save_data.get("world", {})
            meta_data = save_data.get("meta", {})
            seed = int(world_data.get("seed"))
            world_name = str(meta_data.get("world_name") or "World")
            self.window.show_view(GameView(seed=seed, world_name=world_name, save_data=save_data))
        except Exception as exc:
            if self.status_label is not None:
                self._status_text = f"Load failed: {exc}"
                self.status_label.text = self._status_text
                self.status_label.trigger_full_render()

    def _on_delete(self, file_name: str):
        try:
            deleted = delete_save(file_name)
            self._status_text = f"Deleted: {deleted.name}"
        except Exception as exc:
            self._status_text = f"Delete failed: {exc}"
        self._build_ui()

    def _on_load_selected(self, event):
        if not self._selected_file_name:
            self._status_text = "Please select a world first"
            if self.status_label is not None:
                self.status_label.text = self._status_text
                self.status_label.trigger_full_render()
            return
        self._on_load(self._selected_file_name)

    def _on_delete_selected(self, event):
        if not self._selected_file_name:
            self._status_text = "Please select a world first"
            if self.status_label is not None:
                self.status_label.text = self._status_text
                self.status_label.trigger_full_render()
            return
        self._on_delete(self._selected_file_name)

    def _on_back(self, event):
        if self.window is None:
            return
        from start_menu_view import StartMenuView

        self.window.show_view(StartMenuView())

    def on_key_press(self, symbol: int, modifiers: int):
        if symbol == arcade.key.ESCAPE:
            self._on_back(None)
        elif symbol == arcade.key.ENTER:
            self._on_load_selected(None)
        elif symbol == arcade.key.DELETE:
            self._on_delete_selected(None)
