"""Minecraft-artige Hotbar für den Spieler."""

import arcade


class Hotbar:
    """Zeichnet die 9-Slot-Hotbar unten links am Bildschirm."""

    def __init__(self, player):
        self.player = player
        self.slot_size = 52
        self.slot_gap = 8
        self.slot_x_start = 20
        self.slot_y = 20

    def draw(self):
        """Zeichnet die Hotbar und den aktuell ausgewählten Slot."""
        for index in range(self.player.inventory.HOTBAR_SIZE):
            slot_x = self.slot_x_start + index * (self.slot_size + self.slot_gap)
            selected = index == self.player.selected_hotbar_slot
            fill_color = (30, 30, 30, 180) if not selected else (50, 50, 50, 220)
            border_color = arcade.color.WHITE if selected else (200, 200, 200, 150)
            border_width = 3 if selected else 2

            arcade.draw_rect_filled(
                arcade.rect.XYWH(
                    slot_x + self.slot_size / 2,
                    self.slot_y + self.slot_size / 2,
                    self.slot_size,
                    self.slot_size,
                ),
                fill_color,
            )
            arcade.draw_rect_outline(
                arcade.rect.XYWH(
                    slot_x + self.slot_size / 2,
                    self.slot_y + self.slot_size / 2,
                    self.slot_size,
                    self.slot_size
                ),
                border_color,
                border_width,
            )

            block_id = self.player.inventory.get_hotbar_item(index)
            if block_id is None:
                continue

            texture = self.player.inventory.get_texture(block_id)
            if texture is not None:
                rect = arcade.XYWH(
                    slot_x + self.slot_size / 2,
                    self.slot_y + self.slot_size / 2 + 3,
                    24,
                    24,
                )
                arcade.draw_texture_rect(texture, rect, alpha=255)

            arcade.draw_text(
                str(index + 1),
                slot_x + 8,
                self.slot_y + self.slot_size - 18,
                arcade.color.WHITE,
                12,
                anchor_x="left",
                anchor_y="top",
            )

            slot = self.player.inventory.slots[self.player.inventory.HOTBAR_START + index]
            count = slot.count if slot.item is not None else 0
            if count > 0:
                arcade.draw_text(
                    str(count),
                    slot_x + self.slot_size - 8,
                    self.slot_y + 8,
                    arcade.color.WHITE,
                    12,
                    anchor_x="right",
                    anchor_y="bottom",
                )
