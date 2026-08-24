"""Spielerlogik für Pinecraft.

Der Spieler erbt von AnimatedSprite und nutzt damit eine eigene
Animationshierarchie, während die tatsächliche SpriteList im Spiel-Fenster
gezeichnet wird.
"""

from pathlib import Path

import arcade

from animated_sprite import AnimatedSprite
from blocks import AIR, DIRT, GRASS, STONE, get_block_drop_id, get_block_hardness, is_block_breakable, is_block_solid
from items import PICKAXE, TORCH
from inventory import Inventory
from settings import (
    GROUND_Y,
    GRAVITY,
    PLAYER_HEIGHT,
    PLAYER_JUMP_SPEED,
    PLAYER_SPEED,
    PLAYER_START_X,
    PLAYER_START_Y,
    PLAYER_WIDTH,
    TARGET_FPS,
    TILE_SIZE,
)
from sprite_animation import SpriteAnimation
from world import World, world_to_chunk_and_local


def _character_frames(*file_names):
    """Lädt eine Liste von Charakter-Texturen aus dem assets-Verzeichnis."""
    base_dir = Path(__file__).resolve().parent / "assets" / "textures" / "characters"
    return [arcade.load_texture(base_dir / name) for name in file_names]


class Player(AnimatedSprite):
    """Ein einfacher Spieler mit animierbaren Zuständen."""

    BASE_MINING_DURATION = 1.5

    def __init__(self, world: World):
        self.is_mining = False
        self.mining_finished = False

        animations = {
            "idle": SpriteAnimation(_character_frames("steve_idle.png"), fps=1, loop=True),
            "walking": SpriteAnimation(
                _character_frames("steve_walk01.png", "steve_walk02.png"),
                fps=4.0,
                loop=True,
            ),
            "jumping": SpriteAnimation(_character_frames("steve_jump.png"), fps=1, loop=False),
            "mining": SpriteAnimation(
                _character_frames("steve_mining01.png", "steve_mining02.png"),
                fps=5.0, loop=True),
        }

        super().__init__(animations=animations, default_state="idle")

        self.world = world
        self.width = PLAYER_WIDTH
        self.height = PLAYER_HEIGHT
        self.collision_width = animations["idle"].frames[0].width
        self.collision_height = animations["idle"].frames[0].height
        self.center_x = PLAYER_START_X
        self.center_y = PLAYER_START_Y
        self.change_x = 0.0
        self.change_y = 0.0
        self.on_ground = True
        self.state = self.current_state
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.inventory = Inventory({GRASS: 12, DIRT: 12, STONE: 12})
        hotbar_start = self.inventory.HOTBAR_START
        self.inventory.slots[hotbar_start + 0].item = PICKAXE
        self.inventory.slots[hotbar_start + 0].count = 1
        self.inventory.slots[hotbar_start + 1].item = TORCH
        self.inventory.slots[hotbar_start + 1].count = 12
        self.inventory.slots[hotbar_start + 2].item = STONE
        self.inventory.slots[hotbar_start + 2].count = 12
        self.inventory.slots[hotbar_start + 3].item = GRASS
        self.inventory.slots[hotbar_start + 3].count = 12
        self.inventory.slots[hotbar_start + 4].item = DIRT
        self.inventory.slots[hotbar_start + 4].count = 12
        self.inventory.slots[hotbar_start + 5].item = STONE
        self.inventory.slots[hotbar_start + 5].count = 12
        self.inventory.slots[hotbar_start + 6].item = GRASS
        self.inventory.slots[hotbar_start + 6].count = 12
        self.inventory.slots[hotbar_start + 7].item = DIRT
        self.inventory.slots[hotbar_start + 7].count = 12
        self.inventory.slots[hotbar_start + 8].item = STONE
        self.inventory.slots[hotbar_start + 8].count = 12
        self.selected_hotbar_slot = 0
        self.held_item_size = 16
        # Dummy-Positionen pro Zustand/Frame in Bildkoordinaten.
        # Format je Eintrag:
        # {
        #   "x": <bild_x>,
        #   "y": <bild_y>,
        #   "rotation": <grad>,
        #   "scale": <faktor>,
        #   "z_offset": <layer-offset>
        # }
        # Ursprung oben links (wie im Bildeditor).
        # x/y bezeichnen die Position des Anchor-Punkts im Frame.
        # z_offset < 0: hinter dem Spieler zeichnen, >= 0: vor dem Spieler.
        self.held_item_positions = {
            "idle": [{"x": 9, "y": 38, "rotation": 0, "scale": 1.0, "z_offset": 0}],
            "walking": [
                {"x": 35, "y": 37, "rotation": 0, "scale": 1.0, "z_offset": 0},
                {"x": 7, "y": 36, "rotation": 0, "scale": 1.0, "z_offset": 0},
            ],
            "jumping": [{"x": 4, "y": 3, "rotation": 0, "scale": 1.0, "z_offset": 0}],
            "mining": [
                {"x": 41, "y": 37, "rotation": 0, "scale": 1.0, "z_offset": 0},
                {"x": 44, "y": 34, "rotation": 45, "scale": 1.0, "z_offset": 0},
            ],
        }
        # Zusätzliche Render-Modifikatoren je Item-Typ.
        # x/y sind Offsets in Bildkoordinaten relativ zur Pose.
        self.held_item_type_modifiers = {
            # anchor_x/anchor_y sind normalisiert: 0..1 im Item-Quad (0,0 oben links).
            "tool": {
                "scale": 1.5,
                "anchor_x": 0,
                "anchor_y": 1,
            },
            "light": {
                "scale": 2.0,
                "anchor_x": 0.5,
                "anchor_y": 1.0,
            },
        }
        self._held_texture_flip_cache = {}
        self.mining_target = None
        self.is_mining = False
        self.mining_finished = False
        self.pending_item_drops: list[tuple[int, int, int]] = []
        self.world_dirty = False
        self.dirty_chunk_xs: set[int] = set()
        self.mining_animation = SpriteAnimation(
            [
                arcade.load_texture(Path(__file__).resolve().parent / "assets" / "textures" / "cracks" / "crack1.png"),
                arcade.load_texture(Path(__file__).resolve().parent / "assets" / "textures" / "cracks" / "crack2.png"),
                arcade.load_texture(Path(__file__).resolve().parent / "assets" / "textures" / "cracks" / "crack3.png"),
                arcade.load_texture(Path(__file__).resolve().parent / "assets" / "textures" / "cracks" / "crack4.png"),
                arcade.load_texture(Path(__file__).resolve().parent / "assets" / "textures" / "cracks" / "crack5.png"),
            ],
            fps=5.0 / self.BASE_MINING_DURATION,
            loop=False,
        )

        if self.world is not None:
            self.center_y = self.world.get_ground_top(int(self.center_x)) + self.height / 2 + 4

    def set_state(self, state_name):
        """Wechselt nur dann in einen neuen Zustand, wenn nicht gerade gegraben wird."""
        if state_name not in self.animations:
            return

        if self.is_mining and state_name != "mining":
            return

        if self.current_state == state_name and self.current_animation is self.animations[state_name]:
            return

        super().set_state(state_name)
        self.state = self.current_state

    def _set_mining_duration(self, duration_seconds: float):
        """Setzt die Dauer der Mining-Crack-Animation über ihre FPS."""
        duration = max(0.01, float(duration_seconds))
        frame_count = max(1, len(self.mining_animation.frames))
        self.mining_animation.fps = frame_count / duration

    @property
    def selected_block(self):
        """Abwärtskompatibel: liefert nur die platzierbare Block-ID oder None."""
        selected_entry = self.inventory.get_hotbar_item(self.selected_hotbar_slot)
        place_target = self.inventory.get_place_target(selected_entry)
        if place_target is None:
            return None
        target_kind, target_id = place_target
        if target_kind == "block":
            return target_id
        return None

    @property
    def selected_place_target(self):
        """Liefert das aktuelle Platzierungsziel als ('block'|'item', id)."""
        selected_entry = self.inventory.get_hotbar_item(self.selected_hotbar_slot)
        return self.inventory.get_place_target(selected_entry)

    def select_hotbar_slot(self, slot_index: int):
        """Wählt ein Hotbar-Feld aus."""
        if 0 <= slot_index < self.inventory.HOTBAR_SIZE:
            self.selected_hotbar_slot = slot_index

    def _selected_held_entry(self):
        """Liefert die aktuell gehaltene Slot-ID oder None (bei AIR/leer)."""
        selected_entry = self.inventory.get_hotbar_item(self.selected_hotbar_slot)
        if selected_entry is None or selected_entry == AIR:
            return None
        return selected_entry

    def _held_item_image_pose(self):
        """Liefert die aktive Held-Item-Pose in Bildkoordinaten."""
        state_positions = self.held_item_positions.get(self.current_state)
        if not state_positions:
            state_positions = self.held_item_positions.get(
                "idle",
                [{"x": 32, "y": 36, "rotation": 0, "scale": 1.0, "z_offset": 0, "anchor_x": 0.5, "anchor_y": 0.5}],
            )

        frame_index = 0
        if self.current_animation is not None:
            frame_index = getattr(self.current_animation, "frame_index", 0)

        if frame_index >= len(state_positions):
            frame_index = len(state_positions) - 1

        pose = state_positions[frame_index]
        if isinstance(pose, dict):
            x = pose.get("x", 0)
            y = pose.get("y", 0)
            rotation = pose.get("rotation", 0)
            scale = pose.get("scale", 1.0)
            z_offset = pose.get("z_offset", 0)
            anchor_x = pose.get("anchor_x")
            anchor_y = pose.get("anchor_y")
            return x, y, rotation, scale, z_offset, anchor_x, anchor_y

        if isinstance(pose, (tuple, list)):
            if len(pose) >= 3:
                return pose[0], pose[1], pose[2], 1.0, 0, None, None
            if len(pose) == 2:
                return pose[0], pose[1], 0, 1.0, 0, None, None

        return 0, 0, 0, 1.0, 0, None, None

    def _texture_for_facing(self, texture):
        """Liefert je nach Blickrichtung die passende Item-Texture."""
        if self.facing_right:
            return texture

        texture_key = id(texture)
        flipped = self._held_texture_flip_cache.get(texture_key)
        if flipped is not None:
            return flipped

        if hasattr(texture, "flip_left_right"):
            flipped = texture.flip_left_right()
        else:
            flipped = texture

        self._held_texture_flip_cache[texture_key] = flipped
        return flipped

    def draw_held_item(self, layer: str = "front"):
        """Zeichnet das aktuell gewählte Hotbar-Item auf den Spieler."""
        held_entry = self._selected_held_entry()
        if held_entry is None:
            return

        texture = self.inventory.get_texture(held_entry)
        if texture is None:
            return
        texture = self._texture_for_facing(texture)

        frame_texture = self.texture
        if frame_texture is None:
            return

        frame_width = frame_texture.width
        frame_height = frame_texture.height
        if frame_width <= 0 or frame_height <= 0:
            return

        image_x, image_y, item_rotation, item_scale, z_offset, anchor_x, anchor_y = self._held_item_image_pose()
        item_type = self.inventory.get_item_type(held_entry)
        type_modifier = self.held_item_type_modifiers.get(item_type or "", {})

        modifier_x = type_modifier.get("x", 0)
        modifier_y = type_modifier.get("y", 0)
        modifier_rotation = type_modifier.get("rotation", 0)
        modifier_scale = type_modifier.get("scale", 1.0)
        modifier_z = type_modifier.get("z_offset", 0)
        modifier_anchor_x = type_modifier.get("anchor_x")
        modifier_anchor_y = type_modifier.get("anchor_y")

        image_y += modifier_y
        item_rotation += modifier_rotation
        item_scale *= modifier_scale
        z_offset += modifier_z
        if modifier_anchor_x is not None:
            anchor_x = modifier_anchor_x
        elif anchor_x is None:
            anchor_x = 0.5

        if modifier_anchor_y is not None:
            anchor_y = modifier_anchor_y
        elif anchor_y is None:
            anchor_y = 0.5

        if layer == "back" and z_offset >= 0:
            return
        if layer == "front" and z_offset < 0:
            return

        # Spiegelung der Anchor-Position: Rechtslauf misst x von links,
        # Linkslauf misst x von rechts.
        if self.facing_right:
            image_x = image_x + modifier_x
        else:
            image_x = (frame_width - image_x) - modifier_x
            item_rotation = -item_rotation
            anchor_x = 1.0 - anchor_x

        sprite_width = abs(self.width)
        sprite_height = abs(self.height)
        world_left = self.center_x - sprite_width / 2
        world_top = self.center_y + sprite_height / 2

        scale_x = sprite_width / frame_width
        scale_y = sprite_height / frame_height

        held_x = world_left + image_x * scale_x
        held_y = world_top - image_y * scale_y

        item_size = max(1.0, self.held_item_size * item_scale)

        # Der Pose-Punkt ist der gewünschte Anchor-Punkt. Wir berechnen daraus
        # das Zentrum des zu rotierenden Quads, damit die Rotation um den Anchor geht.
        local_anchor_x = (anchor_x - 0.5) * item_size
        local_anchor_y = (0.5 - anchor_y) * item_size
        rot_anchor_x, rot_anchor_y = arcade.math.rotate_point(
            local_anchor_x,
            local_anchor_y,
            0,
            0,
            item_rotation,
        )
        center_x = held_x - rot_anchor_x
        center_y = held_y - rot_anchor_y

        rect = arcade.rect.XYWH(
            center_x,
            center_y,
            item_size,
            item_size,
        )
        arcade.draw_texture_rect(texture, rect, alpha=255, angle=item_rotation)

    def get_equipped_light_source_position(self) -> tuple[float, float] | None:
        """Liefert die Weltposition der Flammenspitze des gehaltenen Light-Items."""
        held_entry = self._selected_held_entry()
        if held_entry is None:
            return None
        if self.inventory.get_item_type(held_entry) != "light":
            return None

        frame_texture = self.texture
        if frame_texture is None:
            return None

        frame_width = frame_texture.width
        frame_height = frame_texture.height
        if frame_width <= 0 or frame_height <= 0:
            return None

        image_x, image_y, item_rotation, item_scale, _z_offset, anchor_x, anchor_y = self._held_item_image_pose()
        type_modifier = self.held_item_type_modifiers.get("light", {})

        modifier_x = type_modifier.get("x", 0)
        modifier_y = type_modifier.get("y", 0)
        modifier_rotation = type_modifier.get("rotation", 0)
        modifier_scale = type_modifier.get("scale", 1.0)
        modifier_anchor_x = type_modifier.get("anchor_x")
        modifier_anchor_y = type_modifier.get("anchor_y")

        image_y += modifier_y
        item_rotation += modifier_rotation
        item_scale *= modifier_scale

        if modifier_anchor_x is not None:
            anchor_x = modifier_anchor_x
        elif anchor_x is None:
            anchor_x = 0.5

        if modifier_anchor_y is not None:
            anchor_y = modifier_anchor_y
        elif anchor_y is None:
            anchor_y = 0.5

        if self.facing_right:
            image_x = image_x + modifier_x
        else:
            image_x = (frame_width - image_x) - modifier_x
            item_rotation = -item_rotation
            anchor_x = 1.0 - anchor_x

        sprite_width = abs(self.width)
        sprite_height = abs(self.height)
        world_left = self.center_x - sprite_width / 2
        world_top = self.center_y + sprite_height / 2

        scale_x = sprite_width / frame_width
        scale_y = sprite_height / frame_height

        held_x = world_left + image_x * scale_x
        held_y = world_top - image_y * scale_y
        item_size = max(1.0, self.held_item_size * item_scale)

        local_anchor_x = (anchor_x - 0.5) * item_size
        local_anchor_y = (0.5 - anchor_y) * item_size
        rot_anchor_x, rot_anchor_y = arcade.math.rotate_point(
            local_anchor_x,
            local_anchor_y,
            0,
            0,
            item_rotation,
        )
        center_x = held_x - rot_anchor_x
        center_y = held_y - rot_anchor_y

        flame_local_x = (0.5 - 0.5) * item_size
        flame_local_y = (0.5 - 0.0) * item_size
        flame_rot_x, flame_rot_y = arcade.math.rotate_point(
            flame_local_x,
            flame_local_y,
            0,
            0,
            item_rotation,
        )
        return center_x + flame_rot_x, center_y + flame_rot_y

    def can_place_block(self, world, tile_x: int, tile_y: int) -> bool:
        """Prüft, ob an der angegebenen Position ein Block oder Item platziert werden kann."""
        if world is None or world.get_block(tile_x, tile_y) != AIR:
            return False
        if world.get_placed_item(tile_x, tile_y) is not None:
            return False

        place_target = self.selected_place_target
        selected_entry = self.inventory.get_hotbar_item(self.selected_hotbar_slot)
        if place_target is None or selected_entry is None or self.inventory.get_item_count(selected_entry) <= 0:
            return False

        support_y = tile_y - 1
        if support_y < 0:
            return False
        support_id = world.get_block(tile_x, support_y)
        if support_id == AIR or not is_block_solid(support_id):
            return False

        block_center_x, block_center_y = world.to_world_position(tile_x, tile_y)
        block_left = block_center_x - TILE_SIZE / 2
        block_right = block_center_x + TILE_SIZE / 2
        block_bottom = block_center_y - TILE_SIZE / 2
        block_top = block_center_y + TILE_SIZE / 2

        sprite_width = abs(self.width)
        sprite_height = abs(self.height)
        player_left = self.center_x - sprite_width / 2
        player_right = self.center_x + sprite_width / 2
        player_bottom = self.center_y - sprite_height / 2
        player_top = self.center_y + sprite_height / 2

        if block_right <= player_left or block_left >= player_right:
            return True
        if block_top <= player_bottom or block_bottom >= player_top:
            return True

        return False

    def place_selected_block(self, world, tile_x: int, tile_y: int) -> bool:
        """Platziert den aktuell ausgewählten Block, falls gültig."""
        if not self.can_place_block(world, tile_x, tile_y):
            return False

        selected_entry = self.inventory.get_hotbar_item(self.selected_hotbar_slot)
        place_target = self.selected_place_target
        if place_target is None or selected_entry is None:
            return False

        target_kind, target_id = place_target

        if self.inventory.get_item_count(selected_entry) <= 0:
            return False

        if target_kind == "block":
            placed = world.place_block(tile_x, tile_y, target_id)
        else:
            placed = world.place_item(tile_x, tile_y, target_id)
        if not placed:
            return False

        self.inventory.remove_item(selected_entry, 1)
        chunk_x, _ = world_to_chunk_and_local(tile_x)
        self.dirty_chunk_xs.add(chunk_x)
        self.world_dirty = True
        return True

    def update(self, delta_time: float):
        """Aktualisiert nur die Animation und löst fertige Mining-Vorgänge selbst aus."""
        if self.is_mining:
            self.mining_animation.update(delta_time)
            if self.mining_animation.has_finished:
                self.mining_finished = True
                self.is_mining = False
                self.release_mining_result(self.world)
                self.world_dirty = self.world is not None

        if self.change_x < 0:
            self.facing_right = False
        elif self.change_x > 0:
            self.facing_right = True

        if self.is_mining:
            self.set_state("mining")
        elif not self.on_ground and self.change_y > 10:
            self.set_state("jumping")
        elif abs(self.change_x) > 0.1:
            self.set_state("walking")
        else:
            self.set_state("idle")

        super().update(delta_time)

    def move_left(self):
        """Bewegt den Spieler nach links."""
        if self.is_mining:
            return
        self.change_x = -PLAYER_SPEED
        self.facing_right = False
        self.scale_x = -1.0
        self.set_state("walking")

    def move_right(self):
        """Bewegt den Spieler nach rechts."""
        if self.is_mining:
            return
        self.change_x = PLAYER_SPEED
        self.facing_right = True
        self.scale_x = 1.0
        self.set_state("walking")

    def stop_horizontal(self):
        """Stoppt die seitliche Bewegung."""
        if self.is_mining:
            return
        self.change_x = 0.0
        if self.on_ground:
            self.set_state("idle")

    def jump(self):
        """Lässt den Spieler springen, wenn er am Boden steht."""
        if self.is_mining:
            return
        if self.on_ground:
            self.change_y = PLAYER_JUMP_SPEED
            self.on_ground = False
            self.set_state("jumping")

    def start_mining(self, block_pos):
        """Startet einen Mining-Vorgang an einer gegebenen Blockposition."""
        if self.is_mining:
            # Wenn die Animation im gleichen Frame bereits fertig ist,
            # Ergebnis zuerst abschließen statt den neuen Klick zu verlieren.
            if self.mining_animation.has_finished:
                self.mining_finished = True
                self.is_mining = False
                self.release_mining_result(self.world)
            else:
                return

        block_id = self.world.get_block(*block_pos)
        if not is_block_breakable(block_id):
            return

        self.facing_right = self.world.to_world_position(*block_pos)[0] > self.center_x

        hardness = get_block_hardness(block_id)
        held_entry = self._selected_held_entry()
        mining_speed = self.inventory.get_mining_speed(held_entry)
        mining_duration = self.BASE_MINING_DURATION * hardness / max(0.01, mining_speed)
        self._set_mining_duration(mining_duration)

        self.mining_target = block_pos
        self.is_mining = True
        self.mining_finished = False
        self.mining_animation.reset()
        self.set_state("mining")

    def cancel_mining(self):
        """Abbrechen des Mining-Vorgangs, wenn die Maustaste vorzeitig losgelassen wird."""
        self.is_mining = False
        self.mining_finished = False
        self.mining_target = None
        self.mining_animation.reset()
        if self.on_ground:
            self.set_state("idle")

    def release_mining_result(self, world=None):
        """Bricht den Block nach dem fertig durchlaufenen Mining-Prozess."""
        if world is None:
            world = self.world

        if world is None or not self.mining_finished or self.mining_target is None:
            return None

        tile_x, tile_y = self.mining_target
        block_id = world.get_block(tile_x, tile_y)
        if block_id == 0:
            self.mining_target = None
            self.mining_finished = False
            self.mining_animation.reset()
            self.world_dirty = False
            return None

        if not is_block_breakable(block_id):
            self.mining_target = None
            self.mining_finished = False
            self.is_mining = False
            self.mining_animation.reset()
            self.world_dirty = False
            return None

        world.break_block(tile_x, tile_y)
        drop_id = get_block_drop_id(block_id)
        if drop_id is None:
            drop_id = block_id
        chunk_x, _ = world_to_chunk_and_local(tile_x)
        self.dirty_chunk_xs.add(chunk_x)
        self.pending_item_drops.append((drop_id, tile_x, tile_y))
        self.mining_target = None
        self.mining_finished = False
        self.is_mining = False
        self.mining_animation.reset()
        self.world_dirty = True
        return block_id

    def consume_pending_item_drops(self) -> list[tuple[int, int, int]]:
        """Liefert und leert alle wartenden Drop-Spawn-Events."""
        if not self.pending_item_drops:
            return []
        pending = self.pending_item_drops
        self.pending_item_drops = []
        return pending

