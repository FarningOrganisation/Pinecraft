"""Inventar-UI für Pinecraft."""

import arcade

from blocks import AIR
from crafting_recipes import CRAFTING_RECIPES
from inventory import InventorySlot


class InventoryUI:
    """Zeichnet das Inventar-Overlay mit Hotbar und Platzhalter-Slots."""

    def __init__(self, player, screen_width=1200, screen_height=420):
        self.player = player
        self.visible = False
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.width = 1000
        self.height = 350
        self.slot_size = 52
        self.slot_gap = 10
        self.crafting_slots = [InventorySlot() for _ in range(9)]

    def toggle(self):
        """Schaltet das Inventar ein oder aus."""
        self.visible = not self.visible

    def _panel_bounds(self):
        """Gibt die Rechteckgrenzen des Inventar-Panels zurück."""
        panel_x = self.screen_width / 2
        panel_y = self.screen_height / 2
        return {
            "left": panel_x - self.width/2,
            "right": panel_x + self.width/2,
            "bottom": panel_y - self.height/2,
            "top": panel_y + self.height/2,
            "center_x": panel_x,
            "center_y": panel_y,
        }

    def _slot_rect(self, index: int):
        """Gibt das Rechteck eines Slots als (left, right, bottom, top) zurück."""
        rows = 4
        cols = 9
        hotbar_gap = 20
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
        result_item, _ = self._crafting_result_info()
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
        for result_item, variants in CRAFTING_RECIPES.items():
            for pattern in variants:
                if len(pattern) != 3 or any(len(recipe_row) != 3 for recipe_row in pattern):
                    continue
                if all(grid[row][col] == pattern[row][col] for row in range(3) for col in range(3)):
                    return result_item, pattern
        return None, None

    def _crafts_possible_for_pattern(self, pattern):
        """Berechnet, wie oft ein passendes Rezept crafted werden kann."""
        crafts_possible = None
        for row in range(3):
            for col in range(3):
                required_item = pattern[row][col]
                index = row * 3 + col
                slot = self.crafting_slots[index]

                if required_item == AIR:
                    if slot.item is not None and slot.count > 0:
                        return 0
                    continue

                if slot.item != required_item or slot.count <= 0:
                    return 0

                if crafts_possible is None:
                    crafts_possible = slot.count
                else:
                    crafts_possible = min(crafts_possible, slot.count)

        return 0 if crafts_possible is None else crafts_possible

    def _crafting_result_info(self):
        """Gibt (Ergebnisitem, Anzahl craftbarer Ergebnisse) zurück."""
        result_item, pattern = self._find_matching_recipe()
        if result_item is None or pattern is None:
            return None, 0

        crafts_possible = self._crafts_possible_for_pattern(pattern)
        if crafts_possible <= 0:
            return None, 0

        return result_item, crafts_possible

    def _consume_crafting_materials(self, crafts_count: int, pattern):
        """Verbraucht Materialien direkt aus den Crafting-Slots."""
        if crafts_count <= 0:
            return

        for row in range(3):
            for col in range(3):
                required_item = pattern[row][col]
                if required_item == AIR:
                    continue
                index = row * 3 + col
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

        inventory = self.player.inventory

        crafting_index = self._get_crafting_slot_at(x, y)
        if crafting_index is not None:
            if button == arcade.MOUSE_BUTTON_LEFT and (modifiers & arcade.key.MOD_SHIFT):
                return False
            if button == arcade.MOUSE_BUTTON_LEFT:
                return self._place_in_crafting_slot(crafting_index)
            if button == arcade.MOUSE_BUTTON_RIGHT:
                self.crafting_slots[crafting_index].item = None
                self.crafting_slots[crafting_index].count = 0
                return True
            return False

        result_rect = self._result_slot_rect()
        if result_rect.left <= x <= result_rect.right and result_rect.bottom <= y <= result_rect.top:
            result_item, crafts_possible = self._crafting_result_info()
            if result_item is None or crafts_possible <= 0:
                return False
            if button == arcade.MOUSE_BUTTON_LEFT:
                remaining = inventory.add_item_to_empty_slots(result_item, crafts_possible)
                crafted = crafts_possible - remaining
                if crafted <= 0:
                    return False
                _, pattern = self._find_matching_recipe()
                if pattern is None:
                    return False
                self._consume_crafting_materials(crafted, pattern)
                return True
            return False

        slot_index = self.get_slot_index_at(x, y)
        if slot_index is None:
            return False

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

    def draw(self):
        """Zeichnet das Inventar-Overlay."""
        if not self.visible:
            return

        panel = self._panel_bounds()
        panel_left = panel["left"]
        panel_right = panel["right"]
        panel_bottom = panel["bottom"]
        panel_top = panel["top"]
        panel_x = panel["center_x"]
        panel_y = panel["center_y"]

        arcade.draw_lrbt_rectangle_filled(
            panel_left,
            panel_right,
            panel_bottom,
            panel_top,
            (15, 15, 20, 210),
        )

        arcade.draw_text(
            "Inventar",
            panel_left + self.slot_size,
            panel_top - 24,
            arcade.color.WHITE,
            18,
            anchor_x="center",
            anchor_y="center",
        )

        inventory = self.player.inventory
        rows = 4
        cols = 9
        grid_left = panel_left + 30
        grid_top = panel_top - 60

        hotbar_gap = 20

        craft_label_x = panel_right - 300
        craft_label_y = panel_top - 24
        arcade.draw_text(
            "Crafting",
            craft_label_x,
            craft_label_y,
            arcade.color.WHITE,
            16,
            anchor_x="left",
            anchor_y="center",
        )

        for index in range(9):
            rect = self._crafting_slot_rect(index)
            arcade.draw_rect_filled(rect, (40, 40, 45, 200))
            arcade.draw_rect_outline(rect, (180, 180, 180, 180), 2)

            slot = self.crafting_slots[index]
            if slot.item is None:
                continue
            texture = self.player.inventory.get_texture(slot.item)
            if texture is not None:
                item_rect = arcade.rect.XYWH(rect.center_x, rect.center_y + 3, 28, 28)
                arcade.draw_texture_rect(texture, item_rect, alpha=255)
            arcade.draw_text(
                str(slot.count),
                rect.right - 8,
                rect.bottom + 8,
                arcade.color.WHITE,
                11,
                anchor_x="right",
                anchor_y="bottom",
            )

        arrow_x = panel_right - 140
        arrow_top = panel_top - 148
        arcade.draw_text("→", arrow_x, arrow_top, arcade.color.WHITE, 36, anchor_x="center", anchor_y="center")

        result_rect = self._result_slot_rect()
        result_item, crafts_possible = self._crafting_result_info()
        result_fill = (40, 40, 45, 200)
        result_border = arcade.color.WHITE if crafts_possible > 0 else (180, 180, 180, 180)
        arcade.draw_rect_filled(result_rect, result_fill)
        arcade.draw_rect_outline(result_rect, result_border, 2)
        if result_item is not None:
            texture = self.player.inventory.get_texture(result_item)
            if texture is not None:
                item_rect = arcade.rect.XYWH(result_rect.center_x, result_rect.center_y + 3, 28, 28)
                arcade.draw_texture_rect(texture, item_rect, alpha=255)
            if crafts_possible > 1:
                arcade.draw_text(
                    str(crafts_possible),
                    result_rect.right - 8,
                    result_rect.bottom + 8,
                    arcade.color.WHITE,
                    11,
                    anchor_x="right",
                    anchor_y="bottom",
                )

        for index in range(inventory.TOTAL_SIZE):
            if index < inventory.HOTBAR_START:
                row = index // cols
                col = index % cols
            else:
                row = rows - 1
                col = index - inventory.HOTBAR_START

            if row >= rows:
                continue

            slot_x = grid_left + col * (self.slot_size + self.slot_gap)
            slot_y = grid_top - row * (self.slot_size + self.slot_gap)
            if index >= inventory.HOTBAR_START:
                slot_y -= hotbar_gap
            rect = arcade.rect.XYWH(slot_x + self.slot_size / 2, slot_y - self.slot_size / 2, self.slot_size, self.slot_size)

            selected = index == inventory.HOTBAR_START + self.player.selected_hotbar_slot and index >= inventory.HOTBAR_START
            fill_color = (40, 40, 45, 200) if not selected else (70, 70, 80, 230)
            border_color = arcade.color.WHITE if selected else (180, 180, 180, 180)

            arcade.draw_rect_filled(rect, fill_color)
            arcade.draw_rect_outline(rect, border_color, 2)

            slot = inventory.get_slot(index)
            if slot is None or slot.item is None:
                continue

            texture = inventory.get_texture(slot.item)
            if texture is not None:
                item_rect = arcade.rect.XYWH(
                    slot_x + self.slot_size / 2,
                    slot_y - self.slot_size / 2 + 3,
                    28,
                    28,
                )
                arcade.draw_texture_rect(texture, item_rect, alpha=255)

            arcade.draw_text(
                str(slot.count),
                slot_x + self.slot_size - 8,
                slot_y - self.slot_size + 8,
                arcade.color.WHITE,
                11,
                anchor_x="right",
                anchor_y="bottom",
            )
