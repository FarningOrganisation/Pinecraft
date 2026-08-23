"""Pinecraft — Milestone 3.

Dieses Projekt enthält jetzt ein einfaches Block- und Chunk-Modell mit
statischer Terrain-Erzeugung. Der Spieler bleibt weiterhin das zentrale
Bewegungselement, während die Welt als einfache, deterministische
Chunk-Struktur aufgebaut wird.
"""

from pathlib import Path

import arcade

from blocks import AIR
from hotbar import Hotbar
from inventory_ui import InventoryUI
from physics import AABBPhysics
from player import Player
from settings import (
    BACKGROUND_COLOR,
    PLAYER_SPEED,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TILE_SIZE,
    WINDOW_TITLE,
)
from world import World
from world_generation import build_world_sprite_list


class GameWindow(arcade.Window):
    """Ein kleines Spiel-Fenster mit Spieler und generierter Welt."""

    def __init__(self):
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, WINDOW_TITLE)
        arcade.set_background_color(BACKGROUND_COLOR)
        self.world = World()
        self.player = Player(world=self.world)
        self.player_sprite_list = arcade.SpriteList()
        self.player_sprite_list.append(self.player)
        self.mining_sprite_list = arcade.SpriteList()
        self.mining_sprite_list.append(self.player.mining_animation)
        self.hotbar = Hotbar(self.player)
        self.inventory_ui = InventoryUI(self.player, SCREEN_WIDTH, SCREEN_HEIGHT)
        self.world_sprite_list = arcade.SpriteList()
        self.camera = arcade.Camera2D()
        self.ui_camera = arcade.Camera2D()
        self.physics = AABBPhysics(self.world)
        self.last_world_center_x = 0.0
        self.frame_count = 0
        self.left_pressed = False
        self.right_pressed = False
        self.break_range = 2.5 * TILE_SIZE

    def _get_local_blocks(self, left: float, right: float, bottom: float, top: float):
        """Gibt nur die relevanten Blöcke um den Spieler zurück."""
        for tile_x, tile_y, block_left, block_right, block_bottom, block_top in self.world.get_blocks_around(
            left, right, bottom, top
        ):
            yield tile_x, tile_y, block_left, block_right, block_bottom, block_top

    def setup(self):
        """Initialisiert den Spielzustand."""
        self.frame_count = 0
        self.world = World()
        self.player = Player(world=self.world)
        self.player.center_x = SCREEN_WIDTH / 2
        ground_y = self.world.get_ground_top(int(self.player.center_x))
        self.player.center_y = ground_y + self.player.height / 2
        self.player.change_x = 0.0
        self.player.change_y = 0.0
        self.player.on_ground = True
        self.player_sprite_list = arcade.SpriteList()
        self.player_sprite_list.append(self.player)
        self.mining_sprite_list = arcade.SpriteList()
        self.mining_sprite_list.append(self.player.mining_animation)
        self.hotbar = Hotbar(self.player)
        self.inventory_ui = InventoryUI(self.player, SCREEN_WIDTH, SCREEN_HEIGHT)
        self.physics = AABBPhysics(self.world)
        self.last_world_center_x = self.player.center_x
        self.camera.position = (self.player.center_x, self.player.center_y)
        self.world.update_loaded_chunks(self.player.center_x)
        self.world_sprite_list = build_world_sprite_list(self.world, center_world_x=self.player.center_x)

    def on_update(self, delta_time: float):
        """Wird regelmäßig pro Frame aufgerufen."""
        self.frame_count += 1

        if self.left_pressed and not self.right_pressed:
            self.player.move_left()
        elif self.right_pressed and not self.left_pressed:
            self.player.move_right()
        elif self.player.on_ground:
            self.player.stop_horizontal()

        self.physics.update(self.player, delta_time)
        self.player.update(delta_time)

        if self.player.mining_target is not None:
            tile_x, tile_y = self.player.mining_target
            world_x, world_y = self.world.to_world_position(tile_x, tile_y)
            self.player.mining_animation.center_x = world_x
            self.player.mining_animation.center_y = world_y
            self.player.mining_animation.visible = True
        else:
            self.player.mining_animation.visible = False

        self.camera.position = (self.player.center_x, self.player.center_y)

        if self.player.world_dirty:
            self.world_sprite_list = build_world_sprite_list(self.world, center_world_x=self.player.center_x)
            self.player.world_dirty = False

        if abs(self.player.center_x - self.last_world_center_x) > 128:
            self.last_world_center_x = self.player.center_x
            self.world.update_loaded_chunks(self.player.center_x)
            self.world_sprite_list = build_world_sprite_list(self.world, center_world_x=self.player.center_x)

    def _screen_to_world(self, screen_x: float, screen_y: float):
        """Konvertiert Bildschirmkoordinaten in Weltkoordinaten."""
        world_x = self.camera.position[0] + (screen_x - self.width / 2)
        world_y = self.camera.position[1] + (screen_y - self.height / 2)
        return world_x, world_y

    def _get_block_from_mouse(self, screen_x: float, screen_y: float):
        """Gibt den Block unter der Maus in Weltkoordinaten zurück oder None."""
        world_x, world_y = self._screen_to_world(screen_x, screen_y)
        tile_x, tile_y = self.world.to_block_position(world_x, world_y)
        block_id = self.world.get_block(tile_x, tile_y)
        if block_id == AIR:
            return None

        block_center_x, block_center_y = self.world.to_world_position(tile_x, tile_y)
        distance = ((block_center_x - self.player.center_x) ** 2 + (block_center_y - self.player.center_y) ** 2) ** 0.5
        if distance > self.break_range:
            return None

        return tile_x, tile_y, block_id

    def on_draw(self):
        """Zeichnet die Szene und die Minecraft-artige Hotbar."""
        self.clear()
        self.camera.use()

        self.world_sprite_list.draw()
        self.player.draw_held_item(layer="back")
        self.player_sprite_list.draw()
        self.player.draw_held_item(layer="front")
        self.mining_sprite_list.draw()

        self.ui_camera.use()
        self.hotbar.draw()
        self.inventory_ui.draw()

        arcade.draw_text(
            "Milestone 8: Hotbar & Placement",
            self.width / 2,
            self.height - 30,
            arcade.color.WHITE,
            20,
            anchor_x="center",
            anchor_y="center",
        )

        inventory_text = " | ".join(
            f"{self.player.inventory.get_display_name(key)}: {value}"
            for key, value in self.player.inventory.items()
        )
        arcade.draw_text(
            inventory_text,
            20,
            self.height - 20,
            arcade.color.WHITE,
            16,
            anchor_x="left",
            anchor_y="top",
        )

        

    def on_key_press(self, symbol: int, modifiers: int):
        """Reagiert auf Tastatureingaben."""
        if 49 <= symbol <= 57:
            slot_index = symbol - 49
            self.player.select_hotbar_slot(slot_index)
            return

        if symbol in (arcade.key.A, arcade.key.LEFT):
            self.left_pressed = True
            self.player.move_left()
        elif symbol in (arcade.key.D, arcade.key.RIGHT):
            self.right_pressed = True
            self.player.move_right()
        elif symbol == arcade.key.SPACE or symbol == arcade.key.UP or symbol == arcade.key.W:
            if self.player.on_ground:
                self.player.jump()
        elif symbol == arcade.key.E:
            self.inventory_ui.toggle()

    def on_key_release(self, symbol: int, modifiers: int):
        """Stoppt die Bewegung bei Tastenloslassen."""
        if symbol in (arcade.key.A, arcade.key.LEFT):
            self.left_pressed = False
        elif symbol in (arcade.key.D, arcade.key.RIGHT):
            self.right_pressed = False

        if not self.left_pressed and not self.right_pressed:
            self.player.stop_horizontal()
        elif self.left_pressed and not self.right_pressed:
            self.player.move_left()
        elif self.right_pressed and not self.left_pressed:
            self.player.move_right()

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        """Verarbeitet Links- und Rechtsklicks für Abbauen, Platzieren und Inventar-Interaktion."""
        if self.inventory_ui.visible:
            self.inventory_ui.handle_click(x, y, button, modifiers)
            return

        if button == arcade.MOUSE_BUTTON_LEFT:
            target = self._get_block_from_mouse(x, y)
            if target is None:
                return

            tile_x, tile_y, _ = target
            self.player.start_mining((tile_x, tile_y))
            return

        if button == arcade.MOUSE_BUTTON_RIGHT:
            world_x, world_y = self._screen_to_world(x, y)
            tile_x, tile_y = self.world.to_block_position(world_x, world_y)
            if self.player.place_selected_block(self.world, tile_x, tile_y):
                self.world_sprite_list = build_world_sprite_list(self.world, center_world_x=self.player.center_x)

    def on_mouse_release(self, x: float, y: float, button: int, modifiers: int):
        """Bricht den Mining-Vorgang ab, wenn die Taste vorzeitig losgelassen wird."""
        if button == arcade.MOUSE_BUTTON_LEFT:
            self.player.cancel_mining()


def main():
    """Startet die Spielschleife."""
    window = GameWindow()
    window.setup()
    arcade.run()


if __name__ == "__main__":
    main()
