# Pinecraft erweitern (Student Guide)

Dieses Dokument zeigt dir, wie du neue Inhalte direkt im Projektcode bauen kannst,
ohne von der Komplexitaet erschlagen zu werden.

## Ziel

Du sollst neue Inhalte in klaren Dateien bauen:

- Bloecke
- Items
- platzierbare Items
- Mobs/Monster/Bosse
- Biome-Variation in der World-Generation

## Hauptdateien fuer Erweiterungen

Diese Dateien sind fuer Erweiterungen gedacht:

- src/ids.py
- src/blocks.py
- src/items.py
- src/crafting_recipes.py
- src/world_gen_config.py
- src/world_generation.py
- src/mobs/mob_template.py
- src/mobs/monster_template.py
- src/mobs/boss_monster_template.py

## Komplexe Core-Dateien

Du darfst diese Dateien bearbeiten, aber starte dort nur mit kleinen Schritten:

- src/game.py
- src/player.py
- src/physics.py
- src/world.py
- src/water.py
- src/lava.py

## 1) Neuer Block

1. Freie Block-ID in src/ids.py aus dem Student-Bereich waehlen.
2. Block in src/blocks.py im BLOCKS-Dictionary eintragen.
3. Texture in assets/textures/blocks ablegen.

Minimalbeispiel:

```python
# ids.py
CUSTOM_BLOCK_BLUE = 16

# blocks.py
BLOCKS[CUSTOM_BLOCK_BLUE] = {
    "name": "Blue Block",
    "texture": "blue_block.png",
    "solid": True,
    "hardness": 1.2,
    "falling": False,
}
```

## 2) Neues Item

1. Freie Item-ID in src/ids.py aus dem Student-Bereich waehlen.
2. Item in src/items.py im ITEMS-Dictionary eintragen.
3. Texture in assets/textures/items ablegen.

```python
# ids.py
CUSTOM_ITEM_CRYSTAL = ITEM_ID_START + 20

# items.py
ITEMS[CUSTOM_ITEM_CRYSTAL] = {
    "item_id": CUSTOM_ITEM_CRYSTAL,
    "name": "Crystal",
    "texture": "crystal.png",
    "item_type": "material",
    "max_stack": 64,
}
```

## 3) Platzierbares Item

Ein platzierbares Item braucht place_as und optional placement_rules.

```python
ITEMS[CUSTOM_ITEM_SIGN] = {
    "item_id": CUSTOM_ITEM_SIGN,
    "name": "Sign",
    "texture": "sign.png",
    "item_type": "nature",
    "max_stack": 64,
    "place_as": "item",
    "placement_rules": {
        "allowed_support_blocks": [GRASS, DIRT],
    },
}
```

## 4) Neues Rezept

Rezepte liegen in src/crafting_recipes.py.

```python
CRAFTING_RECIPES[CUSTOM_ITEM_CRYSTAL] = {
    "pattern": [
        [COBBLESTONE, COBBLESTONE],
        [COBBLESTONE, COBBLESTONE],
    ],
    "count": 1,
}
```

## 5) Neuer Mob / Monster / Boss

Nimm immer ein Template als Start:

- Neutral: src/mobs/mob_template.py
- Hostile: src/mobs/monster_template.py
- Boss: src/mobs/boss_monster_template.py

Wichtig:

1. Datei kopieren und umbenennen.
2. Klasse umbenennen.
3. Mit @register_mob registrieren.
4. In __init__ Texturen und Werte setzen.

Fuer schnelle Tests kannst du in src/game.py die Debug-Spawn-Klasse aendern:

- DEBUG_SPAWN_MOB_CLASS = DeinMob

## 6) Neues Biome-Gefuehl

Fuer den Einstieg musst du keine neue Engine schreiben. Passe zuerst die
Profilwerte in src/world_gen_config.py an:

- biomes (Liste aus BiomeDefinition)
- weight pro Biome (wird normalisiert)
- is_ocean fuer Ocean-Biome
- surface_block_id, subsurface_block_id, deep_block_id
- cave_density_multiplier
- ore_density_multiplier
- sea_level

Tipp: Kleine Aenderungen (5-10%) machen, starten, vergleichen.

## Vorgehensweise in kleinen Schritten

1. Eine Aenderung machen.
2. Spiel starten.
3. Kurz testen.
4. Erst dann naechste Aenderung.

So bleibt dein Build stabil und du lernst schneller, welcher Parameter was bewirkt.

## Fruehe Fehler-Hinweise

Beim Start bekommst du direkte Hinweise im Terminal, wenn Inhalte ungueltig sind:

- [blocks][hint] bei fehlerhaften Block-Definitionen
- [items][hint] bei fehlerhaften Item-Definitionen
- [crafting][hint] bei fehlerhaften Rezepten
- [worldgen][hint] bei problematischen Worldgen-Parametern
