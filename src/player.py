"""Spielerlogik für Pinecraft.

Der Spieler erbt von AnimatedSprite und nutzt damit eine eigene
Animationshierarchie, während die tatsächliche SpriteList im Spiel-Fenster
gezeichnet wird.
"""

import math
import random

import arcade

from animated_sprite import AnimatedSprite
from resource_manager import resource_manager
from blocks import (
    get_block_drop_chance,
    get_block_drop_id, 
    get_block_hardness, 
    is_background_block,
    is_block_breakable, 
    is_block_solid
)
from ids import AIR, DIRT, GRASS, OAK, SAND, STONE, STONE_PICKAXE, STONE_SWORD, TORCH
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
from paths import textures_dir
from sprite_animation import SpriteAnimation
from world import World, world_to_chunk_and_local


def _character_frames(*file_names):
    """Lädt eine Liste von Charakter-Texturen aus dem assets-Verzeichnis."""
    base_dir = textures_dir("characters")
    return [resource_manager.load_texture(base_dir / name) for name in file_names]


class Player(AnimatedSprite):
    """Ein einfacher Spieler mit animierbaren Zuständen."""

    BASE_MINING_DURATION = 1.5
    SWIM_SPEED_FACTOR = 0.58
    SWIM_GRAVITY_FACTOR = 0.36
    SWIM_UP_ACCELERATION = 980.0
    SWIM_MAX_RISE_SPEED = 230.0
    SWIM_SURFACE_HOP_SPEED = 365.0
    WATER_CONTACT_THRESHOLD = 0.04
    MAX_AIR_BUBBLES = 10
    BUBBLE_POP_INTERVAL = 0.75
    DROWNING_DAMAGE_INTERVAL = 1.0

    def __init__(self, world: World):
        self.is_mining = False
        self.mining_finished = False
        self.is_attacking = False

        animations = {
            "idle": SpriteAnimation(_character_frames("steve_idle.png"), fps=1, loop=True),
            "walking": SpriteAnimation(
                _character_frames("steve_walk01.png", "steve_walk02.png"),
                fps=4.0,
                loop=True,
            ),
            "jumping": SpriteAnimation(_character_frames("steve_jump.png"), fps=1, loop=False),
            "attacking": SpriteAnimation(
                _character_frames("steve_mining01.png", "steve_mining02.png"),
                fps=5.0,
                loop=True,
            ),
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
        self.state = self.current_animation_state
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.inventory = Inventory({GRASS: 12, DIRT: 12, STONE: 12, SAND: 12})
        hotbar_start = self.inventory.HOTBAR_START
        self.inventory.slots[hotbar_start + 0].item = STONE_PICKAXE
        self.inventory.slots[hotbar_start + 0].count = 1
        self.inventory.slots[hotbar_start + 1].item = TORCH
        self.inventory.slots[hotbar_start + 1].count = 12
        self.inventory.slots[hotbar_start + 2].item = STONE_SWORD
        self.inventory.slots[hotbar_start + 2].count = 1
        self.inventory.slots[hotbar_start + 3].item = DIRT
        self.inventory.slots[hotbar_start + 3].count = 12
        self.inventory.slots[hotbar_start + 3].item = STONE
        self.inventory.slots[hotbar_start + 3].count = 24

        self.selected_hotbar_slot = 0
        self.max_health = 8
        self.health = self.max_health
        self.invincibility_timer = 0.0
        self.in_water = False
        self.feet_in_water = False
        self.water_submersion = 0.0
        self.max_air_bubbles = self.MAX_AIR_BUBBLES
        self.air_bubbles = self.max_air_bubbles
        self.bubble_pop_interval = self.BUBBLE_POP_INTERVAL
        self._bubble_pop_timer = 0.0
        self._drowning_damage_timer = 0.0
        self.held_item_size = 16
        self.attack_hitbox_width = 56.0
        self.attack_hitbox_height = 34.0
        self.attack_hitbox_offset = 22.0
        self.attack_hit_targets: set[int] = set()
        self._fall_reference_y = self.center_y
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
            "attacking": [
                {"x": 41, "y": 37, "rotation": 0, "scale": 1.0, "z_offset": 0},
                {"x": 44, "y": 34, "rotation": 45, "scale": 1.0, "z_offset": 0},
            ],
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
        self._attack_textures = _character_frames("steve_mining01.png", "steve_mining02.png")
        crack_texture_dir = textures_dir("cracks")
        self._crack_textures = [
            resource_manager.load_texture(crack_texture_dir / "crack1.png"),
            resource_manager.load_texture(crack_texture_dir / "crack2.png"),
            resource_manager.load_texture(crack_texture_dir / "crack3.png"),
            resource_manager.load_texture(crack_texture_dir / "crack4.png"),
            resource_manager.load_texture(crack_texture_dir / "crack5.png"),
        ]
        self.attack_animation = SpriteAnimation(self._attack_textures, fps=5.0 / 0.35, loop=False)
        self.attack_animation.visible = False
        self.mining_animation = SpriteAnimation(self._crack_textures, fps=5.0 / self.BASE_MINING_DURATION, loop=False)

        if self.world is not None:
            self.center_y = self.world.get_ground_top(int(self.center_x)) + self.height / 2 + 4

    def set_animation_state(self, state_name):
        """Wechselt nur dann in einen neuen Zustand, wenn nicht gerade gegraben wird."""
        if state_name not in self.animations:
            return

        if self.is_mining and state_name != "mining":
            return

        if self.is_attacking and state_name != "attacking":
            return

        if self.current_animation_state == state_name and self.current_animation is self.animations[state_name]:
            return

        super().set_animation_state(state_name)
        self.state = self.current_animation_state

    def _set_mining_duration(self, duration_seconds: float):
        """Setzt die Dauer der Mining-Crack-Animation über ihre FPS."""
        duration = max(0.01, float(duration_seconds))
        frame_count = max(1, len(self.mining_animation.frames))
        self.mining_animation.fps = frame_count / duration

    def _sync_attack_animation_position(self):
        """Platziert den Attack-Overlay direkt vor dem Spieler."""
        direction = 1 if self.facing_right else -1
        self.attack_animation.center_x = self.center_x + direction * (self.width * 0.5 + self.attack_hitbox_offset)
        self.attack_animation.center_y = self.center_y + self.height * 0.12

    def draw_attack_animation(self):
        """Attack-Overlay deaktiviert; Angriff wirkt nur über Zustand und Hitbox."""
        return

    def get_attack_hitbox(self) -> tuple[float, float, float, float]:
        """Liefert die aktuelle Angriffs-Hitbox als (left, right, bottom, top)."""
        direction = 1 if self.facing_right else -1
        center_x = self.center_x + direction * (self.width * 0.5 + self.attack_hitbox_offset)
        center_y = self.center_y + self.height * 0.10
        left = center_x - self.attack_hitbox_width / 2
        right = center_x + self.attack_hitbox_width / 2
        bottom = center_y - self.attack_hitbox_height / 2
        top = center_y + self.attack_hitbox_height / 2
        return left, right, bottom, top

    @property
    def attack_damage(self) -> int:
        """Liefert den aktuellen Angriffsschaden basierend auf dem ausgerüsteten Tool."""
        held_entry = self._selected_held_entry()
        if held_entry is None:
            return 1

        item_type = self.inventory.get_item_type(held_entry)
        if item_type != "tool":
            return 1

        return self.inventory.get_attack_damage(held_entry)

    def start_attack(self):
        """Startet einen Nahkampfangriff als einmalige Animation."""
        if self.is_mining:
            self.cancel_mining()

        if self.is_attacking:
            self.attack_animation.reset()
            self.attack_hit_targets.clear()
        else:
            self.is_attacking = True

        self.attack_hit_targets.clear()
        self.attack_animation.reset()
        self.attack_animation.visible = True
        self._sync_attack_animation_position()
        self.set_animation_state("attacking")

    def finish_attack(self):
        """Beendet die Attack-Animation und setzt den Zustand zurück."""
        self.is_attacking = False
        self.attack_animation.visible = False
        self.attack_animation.reset()
        self.attack_hit_targets.clear()

    def take_damage(self, amount: int) -> bool:
        """Offizielle Schadensmethode des Spielers; schützt kurzzeitig vor erneutem Schaden."""
        if amount <= 0:
            return False
        if self.invincibility_timer > 0.0:
            return False

        self.health = max(0, self.health - amount)
        self.invincibility_timer = 0.65
        return True

    def apply_damage(self, amount: int) -> bool:
        """Alias für take_damage() für bestehende Aufrufer."""
        return self.take_damage(amount)

    def apply_fall_damage(self):
        """Wendet Fallschaden nach der Landung an."""
        fall_distance = max(0.0, self._fall_reference_y - self.center_y)
        fall_blocks = fall_distance / TILE_SIZE
        if fall_blocks <= 8.0:
            self._fall_reference_y = self.center_y
            return 0

        damage = math.ceil((fall_blocks - 8.0) / 3.0)
        self.apply_damage(damage)
        self._fall_reference_y = self.center_y
        return damage

    def begin_fall_tracking(self):
        """Merkt sich die Höhe, von der ein Fall begonnen hat."""
        self._fall_reference_y = self.center_y

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
        state_positions = self.held_item_positions.get(self.current_animation_state)
        if not state_positions:
            state_positions = self.held_item_positions.get(
                "idle",
                [{"x": 32, "y": 36, "rotation": 0, "scale": 1.0, "z_offset": 0, "anchor_x": 0.5, "anchor_y": 0.5}],
            )

        frame_index = 0
        if self.current_animation is not None:
            frame_index = self.current_animation.frame_index

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

        target_kind, target_id = place_target
        placement_rules = self.inventory.get_placement_rules(target_id) if target_kind == "item" else {}
        allow_background_support = target_kind == "block" and is_background_block(target_id)

        has_support = False
        if target_kind == "item":
            raw_allowed_support = placement_rules.get("allowed_support_blocks") if isinstance(placement_rules, dict) else None
            if isinstance(raw_allowed_support, (list, tuple, set)):
                if tile_y <= 0:
                    return False
                allowed_support_blocks = {
                    int(block_id)
                    for block_id in raw_allowed_support
                    if isinstance(block_id, (int, float))
                }
                below_block = world.get_block(tile_x, tile_y - 1)
                if below_block not in allowed_support_blocks:
                    return False
                has_support = True

        for ny, nx in ((-1, 0), (1, 0), (0, 1), (0, -1)):
            support_x = tile_x - nx
            support_y = tile_y - ny
            if support_y < 0:
                continue
            support_id = world.get_block(support_x, support_y)
            if support_id == AIR:
                continue
            if is_block_solid(support_id) or (allow_background_support and is_background_block(support_id)):
                has_support = True
                break

        if not has_support:
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
        self.invincibility_timer = max(0.0, self.invincibility_timer - delta_time)

        if self.is_mining:
            self.mining_animation.update(delta_time)
            if self.mining_animation.has_finished:
                self.mining_finished = True
                self.is_mining = False
                self.release_mining_result(self.world)
                self.world_dirty = self.world is not None

        if self.is_attacking:
            self.attack_animation.update(delta_time)
            self._sync_attack_animation_position()
            if self.attack_animation.has_finished:
                self.finish_attack()

        if self.change_x < 0:
            self.facing_right = False
        elif self.change_x > 0:
            self.facing_right = True

        if self.is_mining:
            self.set_animation_state("mining")
        elif self.is_attacking:
            self.set_animation_state("attacking")
        elif not self.on_ground and self.change_y > 10:
            self.set_animation_state("jumping")
        elif abs(self.change_x) > 0.1:
            self.set_animation_state("walking")
        else:
            self.set_animation_state("idle")

        super().update(delta_time)

    def move_left(self):
        """Bewegt den Spieler nach links."""
        if self.is_mining or self.is_attacking:
            return
        self.change_x = -self.get_horizontal_speed()
        self.facing_right = False
        self.scale_x = -1.0
        self.set_animation_state("walking")

    def move_right(self):
        """Bewegt den Spieler nach rechts."""
        if self.is_mining or self.is_attacking:
            return
        self.change_x = self.get_horizontal_speed()
        self.facing_right = True
        self.scale_x = 1.0
        self.set_animation_state("walking")

    def stop_horizontal(self):
        """Stoppt die seitliche Bewegung."""
        if self.is_mining or self.is_attacking:
            return
        self.change_x = 0.0
        if self.on_ground:
            self.set_animation_state("idle")

    def jump(self):
        """Lässt den Spieler springen, wenn er am Boden steht."""
        if self.is_mining or self.is_attacking:
            return
        if self.on_ground:
            self.change_y = PLAYER_JUMP_SPEED
            self.on_ground = False
            self.set_animation_state("jumping")

    def get_horizontal_speed(self) -> float:
        """Liefert die seitliche Zielgeschwindigkeit, in Wasser verlangsamt."""
        if self.in_water or self.feet_in_water:
            return PLAYER_SPEED * self.SWIM_SPEED_FACTOR
        return float(PLAYER_SPEED)

    def get_gravity_multiplier(self) -> float:
        """Liefert den Gravitätsfaktor für die Physik (unter Wasser reduziert)."""
        if self.in_water or self.feet_in_water:
            return self.SWIM_GRAVITY_FACTOR
        return 1.0

    def apply_swim_input(self, jump_pressed: bool, delta_time: float) -> None:
        """Erlaubt Auftrieb beim Halten der Sprungtaste unter Wasser."""
        if not jump_pressed:
            return
        if not (self.in_water or self.feet_in_water):
            return
        if self.is_attacking:
            return

        if not self.in_water and self.feet_in_water:
            self.change_y = max(self.change_y, self.SWIM_SURFACE_HOP_SPEED)
            return

        self.change_y = min(
            self.SWIM_MAX_RISE_SPEED,
            self.change_y + self.SWIM_UP_ACCELERATION * max(0.0, float(delta_time)),
        )

    def refresh_water_state(self) -> None:
        """Aktualisiert Wasserkontakt; unter Wasser gilt nur bei eingetauchtem Kopf."""
        if self.world is None:
            self.in_water = False
            self.feet_in_water = False
            self.water_submersion = 0.0
            return

        left = self.center_x - self.collision_width / 2
        right = self.center_x + self.collision_width / 2
        bottom = self.center_y - self.collision_height / 2
        top = self.center_y + self.collision_height / 2

        min_tile_x = int(math.floor(left / TILE_SIZE))
        max_tile_x = int(math.floor((right - 1e-6) / TILE_SIZE))
        min_tile_y = int(math.floor(bottom / TILE_SIZE))
        max_tile_y = int(math.floor((top - 1e-6) / TILE_SIZE))

        player_area = max(1.0, self.collision_width * self.collision_height)
        water_area = 0.0

        for tile_x in range(min_tile_x, max_tile_x + 1):
            for tile_y in range(min_tile_y, max_tile_y + 1):
                amount = self.world.get_water(tile_x, tile_y)
                if amount <= 0.0:
                    continue

                tile_left = tile_x * TILE_SIZE
                tile_right = tile_left + TILE_SIZE
                tile_bottom = tile_y * TILE_SIZE
                tile_water_top = tile_bottom + TILE_SIZE * max(0.0, min(1.0, amount))

                overlap_w = max(0.0, min(right, tile_right) - max(left, tile_left))
                overlap_h = max(0.0, min(top, tile_water_top) - max(bottom, tile_bottom))
                if overlap_w <= 0.0 or overlap_h <= 0.0:
                    continue
                water_area += overlap_w * overlap_h

        self.water_submersion = max(0.0, min(1.0, water_area / player_area))

        def point_is_underwater(world_x: float, world_y: float) -> bool:
            tile_x = int(math.floor(world_x / TILE_SIZE))
            tile_y = int(math.floor(world_y / TILE_SIZE))
            amount = self.world.get_water(tile_x, tile_y)
            if amount <= 0.0:
                return False
            water_top = tile_y * TILE_SIZE + TILE_SIZE * max(0.0, min(1.0, amount))
            return world_y < water_top

        head_probe_y = top - 2.0
        feet_probe_y = bottom + 2.0
        x_samples = (
            left + 2.0,
            self.center_x,
            right - 2.0,
        )
        self.in_water = any(point_is_underwater(sample_x, head_probe_y) for sample_x in x_samples)
        self.feet_in_water = any(point_is_underwater(sample_x, feet_probe_y) for sample_x in x_samples)

    def update_water_breathing(self, delta_time: float) -> None:
        """Lässt Luftblasen unter Wasser nacheinander platzen und verursacht Ertrinken."""
        dt = max(0.0, float(delta_time))
        if not self.in_water:
            self.air_bubbles = self.max_air_bubbles
            self._bubble_pop_timer = 0.0
            self._drowning_damage_timer = 0.0
            return

        self._bubble_pop_timer += dt
        while self.air_bubbles > 0 and self._bubble_pop_timer >= self.bubble_pop_interval:
            self.air_bubbles -= 1
            self._bubble_pop_timer -= self.bubble_pop_interval

        if self.air_bubbles > 0:
            self._drowning_damage_timer = 0.0
            return

        self._drowning_damage_timer += dt
        while self._drowning_damage_timer >= self.DROWNING_DAMAGE_INTERVAL:
            self.take_damage(1)
            self._drowning_damage_timer -= self.DROWNING_DAMAGE_INTERVAL

    def start_mining(self, block_pos):
        """Startet einen Mining-Vorgang an einer gegebenen Blockposition."""
        if self.is_mining:
            # Ein bereits abgeschlossener Grabvorgang darf nicht den nächsten Klick blockieren.
            if self.mining_animation.has_finished:
                self.mining_finished = True
                self.is_mining = False
                self.release_mining_result(self.world)
            else:
                return

        if self.is_attacking:
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
        self.set_animation_state("mining")

    def cancel_mining(self):
        """Abbrechen des Mining-Vorgangs, wenn die Maustaste vorzeitig losgelassen wird."""
        self.is_mining = False
        self.mining_finished = False
        self.mining_target = None
        self.mining_animation.reset()
        if self.on_ground:
            self.set_animation_state("idle")

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
        drop_chance = get_block_drop_chance(block_id)
        chunk_x, _ = world_to_chunk_and_local(tile_x)
        self.dirty_chunk_xs.add(chunk_x)
        if drop_id is not None and random.random() < drop_chance:
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

