"""Inventar-UI für Pinecraft."""

import arcade
import arcade.gui

from blocks import AIR, get_convertible_partner_block_id
from crafting import find_matching_recipe
from crafting_recipes import CRAFTING_RECIPES
from inventory import InventorySlot


class SlotUIWidget(arcade.gui.UIWidget):
    """Darstellung und Event-Handling fuer einen einzelnen Inventar-Slot."""

    def __init__(self, inventory_ui, slot_kind: str, slot_index: int | None = None):
        super().__init__(width=inventory_ui.slot_size, height=inventory_ui.slot_size, size_hint=None)
        self.inventory_ui = inventory_ui
        self.slot_kind = slot_kind
        self.slot_index = slot_index
        self.is_hovered = False
        self.is_pressed = False

    def _contains_point(self, x: float, y: float) -> bool:
        return self.rect.left <= x <= self.rect.right and self.rect.bottom <= y <= self.rect.top

    def on_event(self, event):
        if not self.inventory_ui.visible:
            if self.is_hovered or self.is_pressed:
                self.is_hovered = False
                self.is_pressed = False
                self.trigger_render()
            return super().on_event(event)

        if isinstance(event, arcade.gui.UIMouseMovementEvent):
            hover_now = self._contains_point(event.x, event.y)
            if hover_now != self.is_hovered:
                self.is_hovered = hover_now
                self.trigger_render()
            return super().on_event(event)

        if isinstance(event, arcade.gui.UIMouseDragEvent):
            hover_now = self._contains_point(event.x, event.y)
            if hover_now != self.is_hovered:
                self.is_hovered = hover_now
                self.trigger_render()
            return super().on_event(event)

        if isinstance(event, arcade.gui.UIMousePressEvent):
            if not self._contains_point(event.x, event.y):
                return super().on_event(event)

            self.is_pressed = True
            self.is_hovered = True
            handled = self.inventory_ui.handle_slot_widget_click(
                self.slot_kind,
                self.slot_index,
                event.button,
                event.modifiers,
            )
            self.trigger_render()
            if handled:
                return True

        if isinstance(event, arcade.gui.UIMouseReleaseEvent):
            was_pressed = self.is_pressed
            self.is_pressed = False
            hover_now = self._contains_point(event.x, event.y)
            if hover_now != self.is_hovered or was_pressed:
                self.is_hovered = hover_now
                self.trigger_render()

        return super().on_event(event)

    def _draw_texture_and_count(self, texture, count: int):
        center_x = self.width / 2
        center_y = self.height / 2
        if texture is not None:
            item_rect = arcade.rect.XYWH(center_x, center_y + 3, 28, 28)
            arcade.draw_texture_rect(texture, item_rect, alpha=255)

        if count > 0:
            arcade.draw_text(
                str(count),
                self.width - 8,
                8,
                arcade.color.WHITE,
                11,
                anchor_x="right",
                anchor_y="bottom",
            )

    def do_render(self, surface):
        if not self.inventory_ui.visible:
            return

        if self.slot_kind == "inventory":
            if self.slot_index is None:
                return
            index = self.slot_index
            inventory = self.inventory_ui.player.inventory
            selected = index == inventory.HOTBAR_START + self.inventory_ui.player.selected_hotbar_slot and index >= inventory.HOTBAR_START
            fill_color = (40, 40, 45, 200) if not selected else (70, 70, 80, 230)
            border_color = arcade.color.WHITE if selected else (180, 180, 180, 180)
            if self.is_hovered:
                fill_color = (56, 56, 64, 220) if not selected else (86, 86, 98, 240)
                border_color = (235, 235, 235, 230)
            if self.is_pressed:
                fill_color = (32, 32, 38, 235) if not selected else (60, 60, 72, 245)
                border_color = (255, 255, 255, 255)

            local_rect = arcade.rect.XYWH(self.width / 2, self.height / 2, self.width, self.height)
            arcade.draw_rect_filled(local_rect, fill_color)
            arcade.draw_rect_outline(local_rect, border_color, 2)

            slot = inventory.get_slot(index)
            if slot is None or slot.item is None:
                return

            texture = inventory.get_texture(slot.item)
            self._draw_texture_and_count(texture, slot.count)
            return

        if self.slot_kind == "crafting":
            if self.slot_index is None:
                return
            index = self.slot_index
            fill_color = (40, 40, 45, 200)
            border_color = (180, 180, 180, 180)
            if self.is_hovered:
                fill_color = (56, 56, 64, 220)
                border_color = (225, 225, 225, 220)
            if self.is_pressed:
                fill_color = (32, 32, 38, 235)
                border_color = (255, 255, 255, 255)
            local_rect = arcade.rect.XYWH(self.width / 2, self.height / 2, self.width, self.height)
            arcade.draw_rect_filled(local_rect, fill_color)
            arcade.draw_rect_outline(local_rect, border_color, 2)

            slot = self.inventory_ui.crafting_slots[index]
            if slot.item is None:
                return

            texture = self.inventory_ui.player.inventory.get_texture(slot.item)
            self._draw_texture_and_count(texture, slot.count)
            return

        if self.slot_kind == "result":
            result_item, output_count, crafts_possible, _, _ = self.inventory_ui._crafting_result_info()
            result_fill = (40, 40, 45, 200)
            result_border = arcade.color.WHITE if crafts_possible > 0 else (180, 180, 180, 180)
            if self.is_hovered:
                result_fill = (56, 56, 64, 220)
                if crafts_possible > 0:
                    result_border = (255, 255, 255, 255)
            if self.is_pressed:
                result_fill = (32, 32, 38, 235)
                if crafts_possible > 0:
                    result_border = (255, 255, 255, 255)
            local_rect = arcade.rect.XYWH(self.width / 2, self.height / 2, self.width, self.height)
            arcade.draw_rect_filled(local_rect, result_fill)
            arcade.draw_rect_outline(local_rect, result_border, 2)

            if result_item is None:
                return

            texture = self.inventory_ui.player.inventory.get_texture(result_item)
            count = output_count if output_count > 1 else 0
            self._draw_texture_and_count(texture, count)
            return

        if self.slot_kind == "conversion_input":
            fill_color = (40, 40, 45, 200)
            border_color = (180, 180, 180, 180)
            if self.is_hovered:
                fill_color = (56, 56, 64, 220)
                border_color = (225, 225, 225, 220)
            if self.is_pressed:
                fill_color = (32, 32, 38, 235)
                border_color = (255, 255, 255, 255)

            local_rect = arcade.rect.XYWH(self.width / 2, self.height / 2, self.width, self.height)
            arcade.draw_rect_filled(local_rect, fill_color)
            arcade.draw_rect_outline(local_rect, border_color, 2)

            slot = self.inventory_ui.conversion_input_slot
            if slot.item is None:
                return

            texture = self.inventory_ui.player.inventory.get_texture(slot.item)
            self._draw_texture_and_count(texture, slot.count)
            return

        if self.slot_kind == "conversion_output":
            output_item, output_count = self.inventory_ui._conversion_result_info()
            fill_color = (40, 40, 45, 200)
            border_color = arcade.color.WHITE if output_item is not None else (180, 180, 180, 180)
            if self.is_hovered:
                fill_color = (56, 56, 64, 220)
                if output_item is not None:
                    border_color = (255, 255, 255, 255)
            if self.is_pressed:
                fill_color = (32, 32, 38, 235)
                if output_item is not None:
                    border_color = (255, 255, 255, 255)

            local_rect = arcade.rect.XYWH(self.width / 2, self.height / 2, self.width, self.height)
            arcade.draw_rect_filled(local_rect, fill_color)
            arcade.draw_rect_outline(local_rect, border_color, 2)

            if output_item is None:
                return

            texture = self.inventory_ui.player.inventory.get_texture(output_item)
            self._draw_texture_and_count(texture, output_count)
            return

        if self.slot_kind == "bin":
            fill_color = (65, 24, 24, 220)
            border_color = (220, 120, 120, 220)
            if self.is_hovered:
                fill_color = (82, 30, 30, 230)
                border_color = (240, 150, 150, 240)
            if self.is_pressed:
                fill_color = (54, 20, 20, 235)
                border_color = (255, 180, 180, 255)

            local_rect = arcade.rect.XYWH(self.width / 2, self.height / 2, self.width, self.height)
            arcade.draw_rect_filled(local_rect, fill_color)
            arcade.draw_rect_outline(local_rect, border_color, 2)

            slot = self.inventory_ui.bin_slot
            if slot.item is None:
                return

            texture = self.inventory_ui.player.inventory.get_texture(slot.item)
            self._draw_texture_and_count(texture, slot.count)


class InventoryUI(arcade.gui.UIAnchorLayout):
    """Zeichnet das Inventar-Overlay mit Hotbar und Platzhalter-Slots."""

    def __init__(self, player, screen_width=1200, screen_height=420):
        panel_width = 1080
        panel_height = 390
        super().__init__(width=panel_width, height=panel_height, size_hint=None)
        self.player = player
        self.visible = False
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.panel_width = panel_width
        self.panel_height = panel_height
        self.slot_size = 52
        self.slot_gap = 10
        self.crafting_slots = [InventorySlot() for _ in range(9)]
        self.conversion_input_slot = InventorySlot()
        self.bin_slot = InventorySlot()
        self._inventory_title_label = None
        self._crafting_title_label = None
        self._crafting_arrow_label = None
        self._conversion_title_label = None
        self._conversion_arrow_label = None
        self._bin_title_label = None
        self._labels_ready = False
        self._ensure_label_widgets()
        self._slot_widgets: list[SlotUIWidget] = []
        self._build_layout_tree()

    def _ensure_label_widgets(self):
        """Erzeugt UILabel-Widgets erst, wenn ein Arcade-Fenster aktiv ist."""
        if self._labels_ready:
            return

        try:
            arcade.get_window()
        except RuntimeError:
            return

        self._inventory_title_label = arcade.gui.UILabel(
            text="Inventar",
            width=220,
            height=28,
            font_size=18,
            text_color=arcade.color.WHITE,
            align="left",
            size_hint=None,
        )
        self._crafting_title_label = arcade.gui.UILabel(
            text="Crafting",
            width=220,
            height=24,
            font_size=16,
            text_color=arcade.color.WHITE,
            align="left",
            size_hint=None,
        )
        self._crafting_arrow_label = arcade.gui.UILabel(
            text="->",
            width=64,
            height=40,
            font_size=36,
            text_color=arcade.color.WHITE,
            align="center",
            size_hint=None,
        )
        self._conversion_title_label = arcade.gui.UILabel(
            text="Block -> Background",
            width=320,
            height=22,
            font_size=15,
            text_color=arcade.color.WHITE,
            align="left",
            size_hint=None,
        )
        self._conversion_arrow_label = arcade.gui.UILabel(
            text="->",
            width=84,
            height=34,
            font_size=26,
            text_color=arcade.color.WHITE,
            align="center",
            size_hint=None,
        )
        self._bin_title_label = arcade.gui.UILabel(
            text="Bin",
            width=52,
            height=22,
            font_size=15,
            text_color=arcade.color.WHITE,
            align="center",
            size_hint=None,
        )
        self._labels_ready = True

    def update_screen_size(self, width: int, height: int):
        """Synchronisiert die Root-Groesse und zentriert das Panel bei Resize."""
        self.screen_width = width
        self.screen_height = height
        self.trigger_full_render()

    def _build_layout_tree(self):
        """Erzeugt AnchorLayout + GridLayouts und Slot-Widgets."""
        self.children.clear()
        self._slot_widgets.clear()

        grid_top_offset = 60
        grid_left_offset = 30
        crafting_grid_left_offset = 650
        grid_to_hotbar_gap = 20
        aligned_row_extra_down = 20
        cols = 9
        top_rows = 3
        inv = self.player.inventory

        main_grid_width = cols * self.slot_size + (cols - 1) * self.slot_gap
        main_grid_height = top_rows * self.slot_size + (top_rows - 1) * self.slot_gap
        hotbar_top_offset = grid_top_offset + main_grid_height + grid_to_hotbar_gap + aligned_row_extra_down

        conversion_top_offset = hotbar_top_offset
        conversion_left_offset = crafting_grid_left_offset
        result_slot_left_offset = 900
        bin_left_offset = result_slot_left_offset

        # Statische Labels als echte GUI-Widgets.
        if self._labels_ready:
            inventory_label = self._inventory_title_label
            crafting_label = self._crafting_title_label
            arrow_label = self._crafting_arrow_label
            conversion_label = self._conversion_title_label
            conversion_arrow_label = self._conversion_arrow_label
            bin_label = self._bin_title_label
            if (
                inventory_label is None
                or crafting_label is None
                or arrow_label is None
                or conversion_label is None
                or conversion_arrow_label is None
                or bin_label is None
            ):
                return

            self.add(
                inventory_label,
                anchor_x="left",
                align_x=grid_left_offset,
                anchor_y="top",
                align_y=-(grid_top_offset - 28),
            )
            self.add(
                crafting_label,
                anchor_x="left",
                align_x=crafting_grid_left_offset,
                anchor_y="top",
                align_y=-(grid_top_offset - 28),
            )
            self.add(
                arrow_label,
                anchor_x="left",
                align_x=self.panel_width - 242,
                anchor_y="top",
                align_y=-122,
            )
            self.add(
                conversion_label,
                anchor_x="left",
                align_x=conversion_left_offset,
                anchor_y="top",
                align_y=-(conversion_top_offset - 24),
            )
            self.add(
                conversion_arrow_label,
                anchor_x="left",
                align_x=conversion_left_offset + 8,
                anchor_y="top",
                align_y=-(conversion_top_offset + 8),
            )
            self.add(
                bin_label,
                anchor_x="left",
                align_x=bin_left_offset,
                anchor_y="top",
                align_y=-(conversion_top_offset - 24),
            )

        main_grid = arcade.gui.UIGridLayout(
            width=main_grid_width,
            height=main_grid_height,
            column_count=cols,
            row_count=top_rows,
            horizontal_spacing=self.slot_gap,
            vertical_spacing=self.slot_gap,
            size_hint=None,
        )
        self.add(
            main_grid,
            anchor_x="left",
            align_x=grid_left_offset,
            anchor_y="top",
            align_y=-grid_top_offset,
        )

        for index in range(inv.HOTBAR_START):
            row = index // cols
            col = index % cols
            grid_row = (top_rows - 1) - row
            slot_widget = SlotUIWidget(self, "inventory", index)
            main_grid.add(slot_widget, column=col, row=grid_row)
            self._slot_widgets.append(slot_widget)

        hotbar_grid = arcade.gui.UIGridLayout(
            width=main_grid_width,
            height=self.slot_size,
            column_count=cols,
            row_count=1,
            horizontal_spacing=self.slot_gap,
            vertical_spacing=self.slot_gap,
            size_hint=None,
        )
        self.add(
            hotbar_grid,
            anchor_x="left",
            align_x=grid_left_offset,
            anchor_y="top",
            align_y=-hotbar_top_offset,
        )

        for hotbar_col in range(inv.HOTBAR_SIZE):
            index = inv.HOTBAR_START + hotbar_col
            slot_widget = SlotUIWidget(self, "inventory", index)
            hotbar_grid.add(slot_widget, column=hotbar_col, row=0)
            self._slot_widgets.append(slot_widget)

        crafting_grid = arcade.gui.UIGridLayout(
            width=3 * self.slot_size + 2 * self.slot_gap,
            height=3 * self.slot_size + 2 * self.slot_gap,
            column_count=3,
            row_count=3,
            horizontal_spacing=self.slot_gap,
            vertical_spacing=self.slot_gap,
            size_hint=None,
        )
        self.add(
            crafting_grid,
            anchor_x="left",
            align_x=crafting_grid_left_offset,
            anchor_y="top",
            align_y=-grid_top_offset,
        )

        for index in range(9):
            row = index // 3
            col = index % 3
            grid_row = 2 - row
            slot_widget = SlotUIWidget(self, "crafting", index)
            crafting_grid.add(slot_widget, column=col, row=grid_row)
            self._slot_widgets.append(slot_widget)

        result_widget = SlotUIWidget(self, "result", None)
        self.add(
            result_widget,
            anchor_x="left",
            align_x=result_slot_left_offset,
            anchor_y="top",
            align_y=-122,
        )
        self._slot_widgets.append(result_widget)

        conversion_input_widget = SlotUIWidget(self, "conversion_input", None)
        self.add(
            conversion_input_widget,
            anchor_x="left",
            align_x=conversion_left_offset,
            anchor_y="top",
            align_y=-conversion_top_offset,
        )
        self._slot_widgets.append(conversion_input_widget)

        conversion_output_widget = SlotUIWidget(self, "conversion_output", None)
        self.add(
            conversion_output_widget,
            anchor_x="left",
            align_x=conversion_left_offset + self.slot_size + 56,
            anchor_y="top",
            align_y=-conversion_top_offset,
        )
        self._slot_widgets.append(conversion_output_widget)

        bin_widget = SlotUIWidget(self, "bin", None)
        self.add(
            bin_widget,
            anchor_x="left",
            align_x=bin_left_offset,
            anchor_y="top",
            align_y=-conversion_top_offset,
        )
        self._slot_widgets.append(bin_widget)

    def toggle(self):
        """Schaltet das Inventar ein oder aus."""
        self.visible = not self.visible
        self.trigger_full_render()

    def handle_slot_widget_click(self, slot_kind: str, slot_index: int | None, button: int, modifiers: int):
        """Verarbeitet Klicks aus dedizierten Slot-Widgets."""
        if slot_kind == "crafting" and slot_index is not None:
            handled = self._handle_crafting_slot_click(slot_index, button, modifiers)
        elif slot_kind == "result":
            handled = self._handle_result_slot_click(button)
        elif slot_kind == "conversion_input":
            handled = self._handle_conversion_input_slot_click(button)
        elif slot_kind == "conversion_output":
            handled = self._handle_conversion_output_slot_click(button)
        elif slot_kind == "bin":
            handled = self._handle_bin_slot_click(button)
        elif slot_kind == "inventory" and slot_index is not None:
            handled = self._handle_inventory_slot_click(slot_index, button, modifiers)
        else:
            handled = False

        if handled:
            self.trigger_full_render()
        return handled

    def _panel_bounds(self):
        """Gibt die Rechteckgrenzen des Inventar-Panels zurück."""
        panel_x = self.rect.center_x
        panel_y = self.rect.center_y
        return {
            "left": panel_x - self.panel_width / 2,
            "right": panel_x + self.panel_width / 2,
            "bottom": panel_y - self.panel_height / 2,
            "top": panel_y + self.panel_height / 2,
            "center_x": panel_x,
            "center_y": panel_y,
        }

    def _slot_rect(self, index: int):
        """Gibt das Rechteck eines Slots als (left, right, bottom, top) zurück."""
        rows = 4
        cols = 9
        hotbar_gap = 40
        player_inventory = self.player.inventory
        panel = self._panel_bounds()
        grid_left = panel["left"] + 30
        grid_top = panel["top"] - 60

        if index < player_inventory.HOTBAR_START:
            row = index // cols
            col = index % cols
        else:
            row = rows - 1
            col = index - player_inventory.HOTBAR_START

        if row >= rows:
            return None

        slot_x = grid_left + col * (self.slot_size + self.slot_gap)
        slot_y = grid_top - row * (self.slot_size + self.slot_gap)
        if index >= player_inventory.HOTBAR_START:
            slot_y -= hotbar_gap
        rect = arcade.rect.XYWH(slot_x + self.slot_size / 2, slot_y - self.slot_size / 2, self.slot_size, self.slot_size)
        return rect

    def _crafting_slot_rect(self, index: int):
        """Gibt das Rechteck eines Crafting-Slots zurück."""
        panel = self._panel_bounds()
        grid_left = panel["right"] - 350
        grid_top = panel["top"] - 60
        col = index % 3
        row = index // 3
        slot_x = grid_left + col * (self.slot_size + self.slot_gap)
        slot_y = grid_top - row * (self.slot_size + self.slot_gap)
        return arcade.rect.XYWH(slot_x + self.slot_size / 2, slot_y - self.slot_size / 2, self.slot_size, self.slot_size)

    def _result_slot_rect(self):
        """Gibt das Rechteck des Crafting-Ergebnis-Slots zurück."""
        panel = self._panel_bounds()
        left = panel["right"] - 100
        top = panel["top"] - 122
        return arcade.rect.XYWH(left + self.slot_size / 2, top - self.slot_size / 2, self.slot_size, self.slot_size)

    def _conversion_input_slot_rect(self):
        """Gibt das Rechteck des Input-Slots fuer die Block-Konvertierung zurueck."""
        panel = self._panel_bounds()
        left = panel["left"] + 650
        top = panel["top"] - (60 + (3 * self.slot_size + 2 * self.slot_gap) + 40)
        return arcade.rect.XYWH(left + self.slot_size / 2, top - self.slot_size / 2, self.slot_size, self.slot_size)

    def _conversion_output_slot_rect(self):
        """Gibt das Rechteck des Output-Slots fuer die Block-Konvertierung zurueck."""
        panel = self._panel_bounds()
        left = panel["left"] + 650 + self.slot_size + 56
        top = panel["top"] - (60 + (3 * self.slot_size + 2 * self.slot_gap) + 40)
        return arcade.rect.XYWH(left + self.slot_size / 2, top - self.slot_size / 2, self.slot_size, self.slot_size)

    def _bin_slot_rect(self):
        """Gibt das Rechteck des Bin-Slots zurück."""
        panel = self._panel_bounds()
        left = panel["right"] - 100
        top = panel["top"] - (60 + (3 * self.slot_size + 2 * self.slot_gap) + 40)
        return arcade.rect.XYWH(left + self.slot_size / 2, top - self.slot_size / 2, self.slot_size, self.slot_size)

    def _handle_crafting_slot_click(self, crafting_index: int, button: int, modifiers: int):
        """Klicklogik fuer einen Crafting-Slot."""
        if button == arcade.MOUSE_BUTTON_LEFT and (modifiers & arcade.key.MOD_SHIFT):
            return False
        if button == arcade.MOUSE_BUTTON_LEFT:
            return self._place_in_crafting_slot(crafting_index)
        if button == arcade.MOUSE_BUTTON_RIGHT:
            self.crafting_slots[crafting_index].item = None
            self.crafting_slots[crafting_index].count = 0
            return True
        return False

    def _handle_result_slot_click(self, button: int):
        """Klicklogik fuer den Crafting-Ergebnis-Slot."""
        if button != arcade.MOUSE_BUTTON_LEFT:
            return False

        inventory = self.player.inventory
        result_item, output_count, crafts_possible, pattern, offset = self._crafting_result_info()
        if result_item is None or output_count <= 0 or crafts_possible <= 0 or pattern is None:
            return False

        remaining = inventory.add_item_to_empty_slots(result_item, output_count)
        if remaining > 0:
            return False

        self._consume_crafting_materials(1, pattern, offset)
        return True

    def _handle_conversion_input_slot_click(self, button: int):
        """Klicklogik fuer den Input-Slot der Block-Hintergrund-Konvertierung."""
        if button == arcade.MOUSE_BUTTON_LEFT:
            return self._place_in_conversion_input_slot()
        if button == arcade.MOUSE_BUTTON_RIGHT:
            self.conversion_input_slot.item = None
            self.conversion_input_slot.count = 0
            return True
        return False

    def _handle_conversion_output_slot_click(self, button: int):
        """Klicklogik fuer den Output-Slot der Block-Hintergrund-Konvertierung."""
        if button != arcade.MOUSE_BUTTON_LEFT:
            return False

        output_item, _ = self._conversion_result_info()
        if output_item is None:
            return False

        inventory = self.player.inventory
        remaining = inventory.add_item(output_item, 1)
        if remaining > 0:
            return False

        self.conversion_input_slot.count -= 1
        if self.conversion_input_slot.count <= 0:
            self.conversion_input_slot.item = None
            self.conversion_input_slot.count = 0
        return True

    def _handle_bin_slot_click(self, button: int):
        """Klicklogik fuer den Bin-Slot."""
        if button != arcade.MOUSE_BUTTON_LEFT:
            return False
        return self._place_in_bin_slot()

    def _handle_inventory_slot_click(self, slot_index: int, button: int, modifiers: int):
        """Klicklogik fuer einen Spieler-Inventar-Slot."""
        inventory = self.player.inventory
        hotbar_start = inventory.HOTBAR_START
        selected_hotbar_index = hotbar_start + self.player.selected_hotbar_slot
        clicked_slot = inventory.get_slot(slot_index)
        if clicked_slot is None:
            return False

        if button == arcade.MOUSE_BUTTON_LEFT and (modifiers & arcade.key.MOD_SHIFT):
            return inventory.merge_same_item(slot_index)

        if button == arcade.MOUSE_BUTTON_RIGHT and (modifiers & arcade.key.MOD_SHIFT):
            return inventory.split_stack(slot_index)

        if slot_index >= hotbar_start:
            if slot_index == selected_hotbar_index:
                return False
            inventory.swap_slots(slot_index, selected_hotbar_index)
            return True

        selected_slot = inventory.get_slot(selected_hotbar_index)
        if clicked_slot.item is None:
            if selected_slot.item is None:
                return False
            clicked_slot.item = selected_slot.item
            clicked_slot.count = selected_slot.count
            selected_slot.item = None
            selected_slot.count = 0
            return True

        if selected_slot.item is None:
            selected_slot.item = clicked_slot.item
            selected_slot.count = clicked_slot.count
            clicked_slot.item = None
            clicked_slot.count = 0
            return True

        inventory.swap_slots(slot_index, selected_hotbar_index)
        return True

    def get_slot_index_at(self, x: float, y: float):
        """Ermittelt den Slot unter einer Mausposition."""
        for index in range(self.player.inventory.TOTAL_SIZE):
            rect = self._slot_rect(index)
            if rect is None:
                continue
            if rect.left <= x <= rect.right and rect.bottom <= y <= rect.top:
                return index
        return None

    def _get_crafting_slot_at(self, x: float, y: float):
        """Ermittelt den Crafting-Slot unter der Mausposition."""
        for index in range(9):
            rect = self._crafting_slot_rect(index)
            if rect.left <= x <= rect.right and rect.bottom <= y <= rect.top:
                return index
        return None

    def _crafting_result_value(self):
        """Gibt das aktuelle Crafting-Ergebnis oder None zurück."""
        result_item, _, _, _, _ = self._crafting_result_info()
        return result_item

    def _current_crafting_grid(self):
        """Liefert den aktuellen 3x3-Crafting-Grid als Block-ID-Matrix."""
        grid = []
        for row in range(3):
            row_values = []
            for col in range(3):
                index = row * 3 + col
                item = self.crafting_slots[index].item
                row_values.append(AIR if item is None else item)
            grid.append(row_values)
        return grid

    def _find_matching_recipe(self):
        """Sucht ein passendes Rezept für den aktuellen 3x3-Grid."""
        grid = self._current_crafting_grid()
        return find_matching_recipe(grid, CRAFTING_RECIPES)

    def _crafts_possible_for_pattern(self, pattern, offset=(0, 0)):
        """Berechnet, wie oft ein passendes Rezept crafted werden kann."""
        crafts_possible = None
        row_offset, col_offset = offset

        for row, pattern_row in enumerate(pattern):
            for col, required_item in enumerate(pattern_row):
                if required_item == AIR:
                    continue

                target_row = row + row_offset
                target_col = col + col_offset
                if target_row < 0 or target_row >= 3 or target_col < 0 or target_col >= 3:
                    return 0

                index = target_row * 3 + target_col
                slot = self.crafting_slots[index]

                if slot.item != required_item or slot.count <= 0:
                    return 0

                if crafts_possible is None:
                    crafts_possible = slot.count
                else:
                    crafts_possible = min(crafts_possible, slot.count)

        return 0 if crafts_possible is None else crafts_possible

    def _crafting_result_info(self):
        """Gibt (Ergebnisitem, Ausgabemenge pro Craft, crafts_possible, pattern, offset) zurück."""
        result_item, pattern, output_count, offset = self._find_matching_recipe()
        if result_item is None or pattern is None or output_count <= 0:
            return None, 0, 0, None, (0, 0)

        used_offset = offset or (0, 0)
        crafts_possible = self._crafts_possible_for_pattern(pattern, used_offset)
        if crafts_possible <= 0:
            return None, 0, 0, None, used_offset

        return result_item, output_count, crafts_possible, pattern, used_offset

    def _consume_crafting_materials(self, crafts_count: int, pattern, offset=(0, 0)):
        """Verbraucht Materialien direkt aus den Crafting-Slots."""
        if crafts_count <= 0:
            return

        row_offset, col_offset = offset

        for row, pattern_row in enumerate(pattern):
            for col, required_item in enumerate(pattern_row):
                if required_item == AIR:
                    continue

                target_row = row + row_offset
                target_col = col + col_offset
                index = target_row * 3 + target_col
                slot = self.crafting_slots[index]
                slot.count -= crafts_count
                if slot.count <= 0:
                    slot.item = None
                    slot.count = 0

    def _clear_crafting(self):
        """Leert alle Crafting-Slots."""
        for index in range(len(self.crafting_slots)):
            self.crafting_slots[index].item = None
            self.crafting_slots[index].count = 0

    def _conversion_result_info(self):
        """Gibt (Ergebnisblock, Anzahl) für die aktive Block-Konvertierung zurück."""
        slot = self.conversion_input_slot
        if slot.item is None or slot.count <= 0:
            return None, 0

        if not self.player.inventory.is_block_id(slot.item):
            return None, 0

        partner_block = get_convertible_partner_block_id(slot.item)
        if partner_block is None:
            return None, 0

        return partner_block, slot.count

    def _place_in_conversion_input_slot(self):
        """Verschiebt Stacks zwischen gewähltem Hotbar-Slot und Konvertierungs-Input."""
        inventory = self.player.inventory
        selected_hotbar_index = inventory.HOTBAR_START + self.player.selected_hotbar_slot
        selected_slot = inventory.get_slot(selected_hotbar_index)
        target_slot = self.conversion_input_slot

        if selected_slot is None:
            return False

        if selected_slot.item is not None:
            is_convertible = (
                inventory.is_block_id(selected_slot.item)
                and get_convertible_partner_block_id(selected_slot.item) is not None
            )
            if not is_convertible:
                return False

            if target_slot.item is None:
                target_slot.item = selected_slot.item
                target_slot.count = selected_slot.count
                selected_slot.item = None
                selected_slot.count = 0
                return True

            if target_slot.item == selected_slot.item:
                target_slot.count += selected_slot.count
                selected_slot.item = None
                selected_slot.count = 0
                return True

            return False

        if target_slot.item is not None:
            selected_slot.item = target_slot.item
            selected_slot.count = target_slot.count
            target_slot.item = None
            target_slot.count = 0
            return True

        return False

    def _place_in_bin_slot(self):
        """Bin-Verhalten: Inhalt entnehmbar, Überlagern verwirft alten Inhalt."""
        inventory = self.player.inventory
        selected_hotbar_index = inventory.HOTBAR_START + self.player.selected_hotbar_slot
        selected_slot = inventory.get_slot(selected_hotbar_index)
        target_slot = self.bin_slot

        if selected_slot is None:
            return False

        if selected_slot.item is not None:
            # Liegt bereits etwas im Bin, wird es beim neuen Ablegen gelöscht.
            target_slot.item = selected_slot.item
            target_slot.count = selected_slot.count
            selected_slot.item = None
            selected_slot.count = 0
            return True

        if target_slot.item is not None:
            selected_slot.item = target_slot.item
            selected_slot.count = target_slot.count
            target_slot.item = None
            target_slot.count = 0
            return True

        return False

    def _place_in_crafting_slot(self, slot_index: int):
        """Verschiebt Stacks zwischen gewähltem Hotbar-Slot und Crafting-Slot."""
        inventory = self.player.inventory
        selected_hotbar_index = inventory.HOTBAR_START + self.player.selected_hotbar_slot
        selected_slot = inventory.get_slot(selected_hotbar_index)

        target_slot = self.crafting_slots[slot_index]

        if selected_slot is None:
            return False

        if selected_slot.item is not None:
            if target_slot.item is None:
                target_slot.item = selected_slot.item
                target_slot.count = selected_slot.count
                selected_slot.item = None
                selected_slot.count = 0
                return True

            if target_slot.item == selected_slot.item:
                target_slot.count += selected_slot.count
                selected_slot.item = None
                selected_slot.count = 0
                return True

            return False

        if target_slot.item is not None:
            selected_slot.item = target_slot.item
            selected_slot.count = target_slot.count
            target_slot.item = None
            target_slot.count = 0
            return True

        return False

    def handle_click(self, x: float, y: float, button: int, modifiers: int):
        """Verarbeitet einen Klick im Inventar-Fenster."""
        if not self.visible:
            return False

        crafting_index = self._get_crafting_slot_at(x, y)
        if crafting_index is not None:
            return self.handle_slot_widget_click("crafting", crafting_index, button, modifiers)

        result_rect = self._result_slot_rect()
        if result_rect.left <= x <= result_rect.right and result_rect.bottom <= y <= result_rect.top:
            return self.handle_slot_widget_click("result", None, button, modifiers)

        conversion_input_rect = self._conversion_input_slot_rect()
        if conversion_input_rect.left <= x <= conversion_input_rect.right and conversion_input_rect.bottom <= y <= conversion_input_rect.top:
            return self.handle_slot_widget_click("conversion_input", None, button, modifiers)

        conversion_output_rect = self._conversion_output_slot_rect()
        if conversion_output_rect.left <= x <= conversion_output_rect.right and conversion_output_rect.bottom <= y <= conversion_output_rect.top:
            return self.handle_slot_widget_click("conversion_output", None, button, modifiers)

        bin_rect = self._bin_slot_rect()
        if bin_rect.left <= x <= bin_rect.right and bin_rect.bottom <= y <= bin_rect.top:
            return self.handle_slot_widget_click("bin", None, button, modifiers)

        slot_index = self.get_slot_index_at(x, y)
        if slot_index is None:
            return False

        return self.handle_slot_widget_click("inventory", slot_index, button, modifiers)

    def on_event(self, event):
        return super().on_event(event)

    def draw(self):
        """Bestehender Draw-Hook bleibt fuer Kompatibilitaet erhalten."""
        return

    def do_render(self, surface):
        if not self.visible:
            return

        if not self._labels_ready:
            self._ensure_label_widgets()
            if self._labels_ready:
                self._build_layout_tree()

        # Transparent lassen, damit die Welt hinter dem Panel sichtbar bleibt.
        surface.clear((0, 0, 0, 0))

        arcade.draw_lrbt_rectangle_filled(
            0,
            self.width,
            0,
            self.height,
            (15, 15, 20, 210),
        )

        super().do_render(surface)
