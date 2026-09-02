"""Zentrale IDs für Blöcke und Items."""

# Block-IDs
AIR = 0
GRASS = 1
DIRT = 2
STONE = 3
BEDROCK = 5
OAK = 6
LEAVES = 7
COAL_ORE = 8
IRON_ORE = 9
GOLD_ORE = 10
DIAMOND_ORE = 11
OAK_PLANKS = 12
COBBLESTONE = 13
SAND = 14
OBSIDIAN = 15

# Item-IDs
ITEM_ID_START = 1024

STONE_PICKAXE = ITEM_ID_START
CHARCOAL = ITEM_ID_START + 1
IRON_INGOT = ITEM_ID_START + 2
GOLD_INGOT = ITEM_ID_START + 3
DIAMOND = ITEM_ID_START + 4
STICK = ITEM_ID_START + 5
TORCH = ITEM_ID_START + 6
STONE_SWORD = ITEM_ID_START + 7
IRON_PICKAXE = ITEM_ID_START + 8
HAMMER = ITEM_ID_START + 9
SAPLING_OAK = ITEM_ID_START + 10
FEATHER = ITEM_ID_START + 11
EGG = ITEM_ID_START + 12

# ---------------------------------------------------------------------------
# Student-Erweiterungsbereiche
# ---------------------------------------------------------------------------
# Diese Bereiche sind fuer eigene Unterrichts-Erweiterungen reserviert,
# damit neue IDs ohne Kollisionen mit dem Core angelegt werden koennen.

# Freie Block-IDs fuer Schuelerprojekte (inklusive Grenzen).
STUDENT_BLOCK_ID_START = 16
STUDENT_BLOCK_ID_END = 63

# Freie Item-IDs fuer Schuelerprojekte (inklusive Grenzen).
STUDENT_ITEM_ID_START = ITEM_ID_START + 20
STUDENT_ITEM_ID_END = ITEM_ID_START + 199

# Beispiel (auskommentiert):
# CUSTOM_BLOCK_MARBLE = STUDENT_BLOCK_ID_START
# CUSTOM_ITEM_MARBLE_SHARD = STUDENT_ITEM_ID_START