"""Pinecraft — Milestone 3.

Dieses Projekt enthält jetzt ein einfaches Block- und Chunk-Modell mit
statischer Terrain-Erzeugung. Der Spieler bleibt weiterhin das zentrale
Bewegungselement, während die Welt als einfache, deterministische
Chunk-Struktur aufgebaut wird.
"""

from pathlib import Path

import arcade

from blocks import AIR, BLOCK_TEXTURES
from dropped_item import DroppedItem
from hotbar import Hotbar
from inventory_ui import InventoryUI
from physics import AABBPhysics
from player import Player
from settings import (
    BACKGROUND_COLOR,
    CHUNK_WIDTH,
    GRAVITY,
    PLAYER_SPEED,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TILE_SIZE,
    WINDOW_TITLE,
)
from world import World, world_to_chunk_and_local
from world_generation import build_chunk_sprite_list


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
        self.dropped_item_sprite_list = arcade.SpriteList()
        self.dropped_items: list[DroppedItem] = []
        self.hotbar = Hotbar(self.player)
        self.inventory_ui = InventoryUI(self.player, SCREEN_WIDTH, SCREEN_HEIGHT)
        self.chunk_sprite_lists: dict[int, arcade.SpriteList] = {}
        self.chunk_sprite_maps: dict[int, dict[tuple[int, int], arcade.Sprite]] = {}
        self.camera = arcade.Camera2D()
        self.ui_camera = arcade.Camera2D()
        self.physics = AABBPhysics(self.world)
        self.render_tile_range: tuple[int, int] | None = None
        self.frame_count = 0
        self.fps_time_accumulator = 0.0
        self.fps_frame_accumulator = 0
        self.fps_display = 0.0
        self.fps_text = arcade.Text(
            text="FPS:   0.0",
            x=20,
            y=self.height - 16,
            color=arcade.color.WHITE,
            font_size=16,
            anchor_x="left",
            anchor_y="top",
        )
        self.max_chunk_loads_per_frame = 1
        self.max_chunk_unloads_per_frame = 1
        self.visible_margin_tiles = 4
        self.render_buffer_tiles = 24
        self.left_pressed = False
        self.right_pressed = False
        self.break_range = 3.5 * TILE_SIZE
        self.item_pull_radius = 4.5 * TILE_SIZE
        self.item_pickup_radius = 0.95 * TILE_SIZE

    def _spawn_dropped_item(self, entry_id: int, tile_x: int, tile_y: int):
        """Erzeugt ein physisches Item an der Blockposition."""
        texture = self.player.inventory.get_texture(entry_id)
        if texture is None:
            return

        spawn_x, spawn_y = self.world.to_world_position(tile_x, tile_y)
        drop = DroppedItem(entry_id=entry_id, texture=texture, spawn_x=spawn_x, spawn_y=spawn_y)
        self.dropped_items.append(drop)
        self.dropped_item_sprite_list.append(drop.sprite)

    def _update_dropped_items(self, delta_time: float):
        """Aktualisiert Drop-Physik und sammelt erreichbare Items auf."""
        if not self.dropped_items:
            return

        preferred_slot = self.player.inventory.HOTBAR_START + self.player.selected_hotbar_slot
        physics_delta = min(delta_time, 1 / 30)

        remaining: list[DroppedItem] = []
        for drop in self.dropped_items:
            wants_pickup = drop.update(
                world=self.world,
                player=self.player,
                delta_time=physics_delta,
                gravity=GRAVITY,
                pull_radius=self.item_pull_radius,
                pickup_radius=self.item_pickup_radius,
            )

            if wants_pickup:
                left = self.player.inventory.add_item(drop.entry_id, 1, preferred_slot_index=preferred_slot)
                if left <= 0:
                    self.dropped_item_sprite_list.remove(drop.sprite)
                    continue

            remaining.append(drop)

        self.dropped_items = remaining

    def _clamped_camera_position(self):
        """Klemmt die Kamera, damit man nicht unter die Welt schauen kann."""
        min_camera_y = self.height / 2
        camera_y = max(self.player.center_y, min_camera_y)
        return self.player.center_x, camera_y

    def _rebuild_world_sprites(self):
        """Erzeugt den Chunk-Sprite-Cache für den aktuellen Sichtbereich neu."""
        min_tile_y, max_tile_y = self._get_target_render_tile_range()
        self.chunk_sprite_lists = {}
        self.chunk_sprite_maps = {}
        for chunk_x in sorted(self.world.chunks):
            chunk = self.world.chunks[chunk_x]
            sprite_list, sprite_map = build_chunk_sprite_list(chunk_x, chunk, min_tile_y, max_tile_y)
            self.chunk_sprite_lists[chunk_x] = sprite_list
            self.chunk_sprite_maps[chunk_x] = sprite_map
        self.render_tile_range = (min_tile_y, max_tile_y)

    def _get_visible_tile_range(self, margin_tiles: int | None = None) -> tuple[int, int]:
        """Berechnet den vertikal sichtbaren Tile-Bereich der Kamera."""
        if margin_tiles is None:
            margin_tiles = self.visible_margin_tiles
        half_h = self.height / 2
        min_tile_y = max(0, int((self.camera.position[1] - half_h) // TILE_SIZE) - margin_tiles)
        max_tile_y = int((self.camera.position[1] + half_h) // TILE_SIZE) + margin_tiles
        return min_tile_y, max_tile_y

    def _get_target_render_tile_range(self) -> tuple[int, int]:
        """Sichtbereich plus Puffer, um häufige Rebuilds beim Springen zu vermeiden."""
        visible_min, visible_max = self._get_visible_tile_range()
        return (
            max(0, visible_min - self.render_buffer_tiles),
            visible_max + self.render_buffer_tiles,
        )

    def _get_visible_chunk_range(self, margin_chunks: int = 1) -> tuple[int, int]:
        """Berechnet den horizontal sichtbaren Chunk-Bereich der Kamera."""
        half_w = self.width / 2
        left_x = self.camera.position[0] - half_w - margin_chunks * CHUNK_WIDTH * TILE_SIZE
        right_x = self.camera.position[0] + half_w + margin_chunks * CHUNK_WIDTH * TILE_SIZE
        min_tile_x = int(left_x // TILE_SIZE)
        max_tile_x = int(right_x // TILE_SIZE)
        min_chunk_x, _ = world_to_chunk_and_local(min_tile_x)
        max_chunk_x, _ = world_to_chunk_and_local(max_tile_x)
        return min_chunk_x, max_chunk_x

    def _sync_chunk_sprite_cache(self, loaded_chunks: list[int], unloaded_chunks: list[int]):
        """Aktualisiert nur die geänderten Chunk-Sprites."""
        for chunk_x in unloaded_chunks:
            self.chunk_sprite_lists.pop(chunk_x, None)
            self.chunk_sprite_maps.pop(chunk_x, None)

        if not loaded_chunks:
            return

        if self.render_tile_range is None:
            min_tile_y, max_tile_y = self._get_target_render_tile_range()
            self.render_tile_range = (min_tile_y, max_tile_y)
        else:
            min_tile_y, max_tile_y = self.render_tile_range

        for chunk_x in loaded_chunks:
            chunk = self.world.chunks.get(chunk_x)
            if chunk is None:
                continue
            sprite_list, sprite_map = build_chunk_sprite_list(chunk_x, chunk, min_tile_y, max_tile_y)
            self.chunk_sprite_lists[chunk_x] = sprite_list
            self.chunk_sprite_maps[chunk_x] = sprite_map

    def _apply_world_block_diffs(self, changes: list[tuple[int, int, int, int]]):
        """Aktualisiert Sprites einzelner geänderter Blöcke ohne Chunk-Rebuild."""
        if not changes:
            return

        if self.render_tile_range is None:
            min_tile_y, max_tile_y = self._get_target_render_tile_range()
            self.render_tile_range = (min_tile_y, max_tile_y)
        else:
            min_tile_y, max_tile_y = self.render_tile_range

        for tile_x, tile_y, _old_block_id, new_block_id in changes:
            chunk_x, local_x = world_to_chunk_and_local(tile_x)
            sprite_list = self.chunk_sprite_lists.get(chunk_x)
            if sprite_list is None:
                continue

            sprite_map = self.chunk_sprite_maps.setdefault(chunk_x, {})
            key = (local_x, tile_y)
            existing_sprite = sprite_map.get(key)

            in_visible_band = min_tile_y <= tile_y <= max_tile_y
            texture = BLOCK_TEXTURES.get(new_block_id)
            should_render = in_visible_band and new_block_id != AIR and texture is not None

            if existing_sprite is not None and not should_render:
                sprite_list.remove(existing_sprite)
                sprite_map.pop(key, None)
                continue

            if not should_render:
                continue

            if texture is None:
                continue

            if existing_sprite is not None:
                existing_sprite.texture = texture
                continue

            sprite = arcade.Sprite(texture)
            sprite.center_x = (chunk_x * self.world.chunks[chunk_x].width + local_x + 0.5) * TILE_SIZE
            sprite.center_y = (tile_y + 0.5) * TILE_SIZE
            sprite.width = TILE_SIZE
            sprite.height = TILE_SIZE
            sprite_list.append(sprite)
            sprite_map[key] = sprite

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
        self.dropped_item_sprite_list = arcade.SpriteList()
        self.dropped_items = []
        self.hotbar = Hotbar(self.player)
        self.inventory_ui = InventoryUI(self.player, SCREEN_WIDTH, SCREEN_HEIGHT)
        self.physics = AABBPhysics(self.world)
        self.chunk_sprite_lists = {}
        self.chunk_sprite_maps = {}
        self.render_tile_range = None
        self.camera.position = self._clamped_camera_position()
        self.world.update_loaded_chunks(self.player.center_x)
        self._rebuild_world_sprites()

    def on_update(self, delta_time: float):
        """Wird regelmäßig pro Frame aufgerufen."""
        self.frame_count += 1
        self.fps_time_accumulator += delta_time
        self.fps_frame_accumulator += 1
        if self.fps_time_accumulator >= 0.25:
            self.fps_display = self.fps_frame_accumulator / self.fps_time_accumulator
            self.fps_time_accumulator = 0.0
            self.fps_frame_accumulator = 0
            self.fps_text.text = f"FPS: {self.fps_display:5.1f}"

        if self.left_pressed and not self.right_pressed:
            self.player.move_left()
        elif self.right_pressed and not self.left_pressed:
            self.player.move_right()
        elif self.player.on_ground:
            self.player.stop_horizontal()

        physics_delta = min(delta_time, 1 / 30)
        self.physics.update(self.player, physics_delta)
        self.player.update(physics_delta)
        for drop_id, tile_x, tile_y in self.player.consume_pending_item_drops():
            self._spawn_dropped_item(drop_id, tile_x, tile_y)
        self._update_dropped_items(physics_delta)

        if self.player.mining_target is not None:
            tile_x, tile_y = self.player.mining_target
            world_x, world_y = self.world.to_world_position(tile_x, tile_y)
            self.player.mining_animation.center_x = world_x
            self.player.mining_animation.center_y = world_y
            self.player.mining_animation.visible = True
        else:
            self.player.mining_animation.visible = False

        self.camera.position = self._clamped_camera_position()

        visible_range = self._get_visible_tile_range()
        did_full_rebuild = False
        if self.render_tile_range is None:
            self._rebuild_world_sprites()
            did_full_rebuild = True
        else:
            render_min, render_max = self.render_tile_range
            visible_min, visible_max = visible_range
            if visible_min < render_min or visible_max > render_max:
                self._rebuild_world_sprites()
                did_full_rebuild = True

        block_changes = self.world.consume_changed_blocks()
        if block_changes and not did_full_rebuild:
            self._apply_world_block_diffs(block_changes)

        if self.player.world_dirty:
            self.player.world_dirty = False
            self.player.dirty_chunk_xs.clear()

        loaded_chunks, unloaded_chunks = self.world.update_loaded_chunks(
            self.player.center_x,
            max_loads=self.max_chunk_loads_per_frame,
            max_unloads=self.max_chunk_unloads_per_frame,
        )
        if loaded_chunks or unloaded_chunks:
            self._sync_chunk_sprite_cache(loaded_chunks, unloaded_chunks)

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

        min_chunk_x, max_chunk_x = self._get_visible_chunk_range()
        for chunk_x in range(min_chunk_x, max_chunk_x + 1):
            chunk_sprites = self.chunk_sprite_lists.get(chunk_x)
            if chunk_sprites is not None:
                chunk_sprites.draw()
        self.dropped_item_sprite_list.draw()
        self.player.draw_held_item(layer="back")
        self.player_sprite_list.draw()
        self.player.draw_held_item(layer="front")
        self.mining_sprite_list.draw()

        self.ui_camera.use()
        self.hotbar.draw()
        self.inventory_ui.draw()
        self.fps_text.y = self.height - 16
        self.fps_text.draw()

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
            self.player.place_selected_block(self.world, tile_x, tile_y)

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
