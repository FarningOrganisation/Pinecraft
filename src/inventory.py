"""Inventar-System für Pinecraft.

Das Inventar verwaltet Slots mit Stapelgrößen und trennt die eigentliche
Logik vom Rendering. Die Hotbar sind die ersten 9 Slots eines größeren
Inventars.
"""

from __future__ import annotations

from dataclasses import dataclass

from blocks import BLOCKS
from entry_textures import get_entry_texture
from ids import AIR, ITEM_ID_START
from items import ITEMS, is_item_id


@dataclass
class InventorySlot:
    """Ein Inventar-Slot mit Item und Anzahl."""

    item: int | None = None
    count: int = 0


class Inventory:
    """Ein einfaches Minecraft-artiges Inventar mit Stapelgrößen."""

    HOTBAR_SIZE = 9
    BACKPACK_SIZE = 27
    TOTAL_SIZE = HOTBAR_SIZE + BACKPACK_SIZE
    HOTBAR_START = TOTAL_SIZE - HOTBAR_SIZE

    def __init__(self, starting_items=None):
        self.slots = [InventorySlot() for _ in range(self.TOTAL_SIZE)]
        if starting_items:
            for item, count in starting_items.items():
                self.add_item(item, count)

    @staticmethod
    def max_stack_for(item):
        """Gibt die maximale Stapelgröße für ein Item zurück."""
        if item == AIR:
            return 0
        if item is None:
            return 0
        if is_item_id(item):
            item_definition = ITEMS.get(item)
            if item_definition is None:
                return 1
            return item_definition.get("max_stack", 1)
        if item in BLOCKS:
            return 64
        return 1

    @staticmethod
    def is_item_id(entry_id):
        """True, wenn die ID im Item-Bereich liegt (>= 1024)."""
        return isinstance(entry_id, int) and entry_id >= ITEM_ID_START

    @staticmethod
    def is_block_id(entry_id):
        """True, wenn die ID ein platzierbarer Block ist."""
        return isinstance(entry_id, int) and entry_id in BLOCKS

    @staticmethod
    def get_place_target(entry_id):
        """Liefert Platzierungsziel als ('block'|'item', id) oder None."""
        if entry_id is None or entry_id == AIR:
            return None
        if Inventory.is_block_id(entry_id):
            return "block", entry_id
        if Inventory.is_item_id(entry_id):
            item_definition = ITEMS.get(entry_id) or {}
            if item_definition.get("place_as") == "item":
                return "item", entry_id
        return None

    @staticmethod
    def get_placement_rules(entry_id) -> dict:
        """Liefert optionale Platzierungsregeln für ein Item."""
        if not Inventory.is_item_id(entry_id):
            return {}
        item_definition = ITEMS.get(entry_id)
        if item_definition is None:
            return {}
        rules = item_definition.get("placement_rules")
        if not isinstance(rules, dict):
            return {}
        return rules

    @staticmethod
    def is_placeable(entry_id):
        """Nur Blöcke sind platzierbar."""
        return Inventory.get_place_target(entry_id) is not None

    @staticmethod
    def get_display_name(entry_id):
        """Liefert den Anzeigenamen für Block oder Item."""
        if entry_id is None or entry_id == AIR:
            return "Air"
        if Inventory.is_item_id(entry_id):
            item_definition = ITEMS.get(entry_id)
            return item_definition.get("name", f"Item {entry_id}") if item_definition is not None else f"Item {entry_id}"
        block_definition = BLOCKS.get(entry_id)
        if block_definition is not None:
            return block_definition["name"]
        return f"Unknown {entry_id}"

    @staticmethod
    def get_entry_kind(entry_id):
        """Liefert block, item oder unknown."""
        if entry_id is None or entry_id == AIR:
            return "unknown"
        if Inventory.is_item_id(entry_id):
            return "item"
        if Inventory.is_block_id(entry_id):
            return "block"
        return "unknown"

    @staticmethod
    def get_item_type(entry_id):
        """Liefert den Item-Typ (consumable/tool/material) für Items."""
        if not Inventory.is_item_id(entry_id):
            return None
        item_definition = ITEMS.get(entry_id)
        if item_definition is None:
            return None
        return item_definition.get("item_type")

    @staticmethod
    def get_mining_speed(entry_id):
        """Liefert den Mining-Speed-Multiplikator eines Eintrags (Default: 1.0)."""
        if not Inventory.is_item_id(entry_id):
            return 1.0
        item_definition = ITEMS.get(entry_id)
        if item_definition is None:
            return 1.0
        speed = item_definition.get("mining_speed", 1.0)
        try:
            speed_value = float(speed)
        except (TypeError, ValueError):
            return 1.0
        return max(0.01, speed_value)

    @staticmethod
    def get_attack_damage(entry_id):
        """Liefert den Angriffsbonus eines Eintrags (Default: 1)."""
        if not Inventory.is_item_id(entry_id):
            return 1
        item_definition = ITEMS.get(entry_id)
        if item_definition is None:
            return 1
        damage = item_definition.get("attack_damage", 1)
        try:
            damage_value = int(damage)
        except (TypeError, ValueError):
            return 1
        return max(1, damage_value)

    @staticmethod
    def get_texture(entry_id):
        """Liefert die passende Texture für Block oder Item."""
        return get_entry_texture(entry_id)

    @property
    def hotbar(self):
        """Gibt die Hotbar-Slots zurück."""
        return self.slots[self.HOTBAR_START :]

    def get_slot(self, index: int):
        """Liefert den Slot an einer Position."""
        if 0 <= index < len(self.slots):
            return self.slots[index]
        return None

    def get_hotbar_item(self, index: int):
        """Liefert das Item im Hotbar-Slot."""
        if 0 <= index < self.HOTBAR_SIZE:
            slot = self.slots[self.HOTBAR_START + index]
            if slot.item is not None and slot.count > 0:
                return slot.item
        return None

    def get_item_count(self, item):
        """Zählt, wie viele Exemplare eines Items im Inventar liegen."""
        if item is None:
            return 0
        return sum(slot.count for slot in self.slots if slot.item == item)

    def items(self):
        """Gibt alle vorhandenen Items mit Gesamtanzahl als dict-like-View zurück."""
        items = {}
        for slot in self.slots:
            if slot.item is None or slot.count <= 0:
                continue
            items[slot.item] = items.get(slot.item, 0) + slot.count
        return items.items()

    def add_item(self, item, count: int = 1, preferred_slot_index: int | None = None) -> int:
        """Fügt Items hinzu und liefert den Rest zurück, falls nocht Platz fehlt.

        Wenn preferred_slot_index gesetzt ist, wird in dieser Reihenfolge eingefügt:
        1) bevorzugter Slot, 2) erster passender Hotbar-Slot,
        3) erster passender Inventar-Slot, 4) erster leerer Hotbar-Slot,
        5) erster leerer Inventar-Slot.
        """
        if item is None or count <= 0:
            return 0

        remaining = count
        max_stack = self.max_stack_for(item)

        if preferred_slot_index is not None:
            def add_to_slot(slot_index: int) -> int:
                if not (0 <= slot_index < len(self.slots)):
                    return 0
                slot = self.slots[slot_index]
                if slot.item not in (None, item):
                    return 0
                if slot.item is None:
                    slot.item = item
                    slot.count = 0
                if slot.count >= max_stack:
                    return 0
                added_local = min(max_stack - slot.count, remaining)
                slot.count += added_local
                return added_local

            added = add_to_slot(preferred_slot_index)
            remaining -= added
            if remaining == 0:
                return 0

            for slot_index in range(self.HOTBAR_START, self.TOTAL_SIZE):
                if slot_index == preferred_slot_index:
                    continue
                slot = self.slots[slot_index]
                if slot.item == item and slot.count < max_stack:
                    added = add_to_slot(slot_index)
                    remaining -= added
                    if remaining == 0:
                        return 0
                    break

            for slot_index in range(0, self.HOTBAR_START):
                slot = self.slots[slot_index]
                if slot.item == item and slot.count < max_stack:
                    added = add_to_slot(slot_index)
                    remaining -= added
                    if remaining == 0:
                        return 0
                    break

            for slot_index in range(self.HOTBAR_START, self.TOTAL_SIZE):
                slot = self.slots[slot_index]
                if slot.item is None:
                    added = min(max_stack, remaining)
                    slot.item = item
                    slot.count = added
                    remaining -= added
                    if remaining == 0:
                        return 0

            for slot_index in range(0, self.HOTBAR_START):
                slot = self.slots[slot_index]
                if slot.item is None:
                    added = min(max_stack, remaining)
                    slot.item = item
                    slot.count = added
                    remaining -= added
                    if remaining == 0:
                        return 0

            return remaining

        for slot in self.slots:
            if slot.item == item and slot.count < max_stack:
                space = max_stack - slot.count
                added = min(space, remaining)
                slot.count += added
                remaining -= added
                if remaining == 0:
                    return 0

        for slot in self.slots:
            if slot.item is None:
                added = min(max_stack, remaining)
                slot.item = item
                slot.count = added
                remaining -= added
                if remaining == 0:
                    return 0

        return remaining

    def add_item_to_empty_slots(self, item, count: int = 1) -> int:
        """Fügt ein Item nur in freie Slots ein und liefert den Rest zurück."""
        if item is None or count <= 0:
            return 0

        remaining = count
        max_stack = self.max_stack_for(item)
        if max_stack <= 0:
            return remaining

        for slot in self.slots:
            if slot.item is not None:
                continue
            added = min(max_stack, remaining)
            slot.item = item
            slot.count = added
            remaining -= added
            if remaining <= 0:
                return 0

        return remaining

    def remove_item(self, item, count: int = 1) -> int:
        """Entfernt Items und liefert die tatsächlich entfernte Menge zurück."""
        if item is None or count <= 0:
            return 0

        removed = 0
        for index in range(len(self.slots) - 1, -1, -1):
            slot = self.slots[index]
            if slot.item != item:
                continue

            take = min(slot.count, count - removed)
            slot.count -= take
            removed += take

            if slot.count <= 0:
                slot.item = None
                slot.count = 0

            if removed >= count:
                break

        return removed

    def swap_slots(self, first_index: int, second_index: int):
        """Vertauscht zwei Slots."""
        if not (0 <= first_index < len(self.slots) and 0 <= second_index < len(self.slots)):
            return
        self.slots[first_index], self.slots[second_index] = self.slots[second_index], self.slots[first_index]

    def clear_slot(self, index: int):
        """Leert einen Slot."""
        if 0 <= index < len(self.slots):
            self.slots[index].item = None
            self.slots[index].count = 0

    def merge_same_item(self, source_index: int, target_index: int | None = None):
        """Verschiebt so viele Items wie möglich in einen passenden Slot."""
        if not (0 <= source_index < len(self.slots)):
            return False

        source_slot = self.slots[source_index]
        if source_slot.item is None or source_slot.count <= 0:
            return False

        if target_index is None:
            for index in range(len(self.slots)):
                if index == source_index:
                    continue
                candidate = self.slots[index]
                if candidate.item == source_slot.item and candidate.count < self.max_stack_for(source_slot.item):
                    target_index = index
                    break

        if target_index is None or not (0 <= target_index < len(self.slots)):
            return False

        target_slot = self.slots[target_index]
        if target_slot.item not in (None, source_slot.item):
            return False

        if target_slot.item is None:
            target_slot.item = source_slot.item
            target_slot.count = 0

        moved = min(source_slot.count, self.max_stack_for(source_slot.item) - target_slot.count)
        if moved <= 0:
            return False

        target_slot.count += moved
        source_slot.count -= moved
        if source_slot.count <= 0:
            source_slot.item = None
            source_slot.count = 0
        return True

    def split_stack(self, index: int):
        """Teilt einen Stack in zwei Hälften und legt die zweite Hälfte auf einen freien passenden Slot."""
        if not (0 <= index < len(self.slots)):
            return False

        slot = self.slots[index]
        if slot.item is None or slot.count <= 1:
            return False

        half = slot.count // 2
        if half <= 0:
            return False

        for candidate_index in range(len(self.slots)):
            if candidate_index == index:
                continue
            candidate = self.slots[candidate_index]
            if candidate.item is None:
                candidate.item = slot.item
                candidate.count = half
                slot.count -= half
                return True
        
        for candidate_index in range(len(self.slots)):
            if candidate_index == index:
                continue
            candidate = self.slots[candidate_index]
            if candidate.item == slot.item and candidate.count < self.max_stack_for(slot.item):
                space = self.max_stack_for(slot.item) - candidate.count
                moved = min(half, space)
                candidate.count += moved
                slot.count -= moved
                if slot.count <= 0:
                    slot.item = None
                    slot.count = 0
                return True

        return False
