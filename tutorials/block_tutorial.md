# Tutorial: Neuer Block

## Ziel

Du fuegst einen neuen Block hinzu, der abgebaut und platziert werden kann.

## Schritte

1. Neue Block-ID in src/ids.py vergeben (im STUDENT_BLOCK_ID Bereich).
2. Blockdefinition in src/blocks.py im BLOCKS-Dictionary hinzufuegen.
3. Texture in assets/textures/blocks ablegen.
4. Spiel starten und testen.

## Minimalbeispiel

```python
# src/ids.py
CUSTOM_BLOCK_BLUE = STUDENT_BLOCK_ID_START

# src/blocks.py
BLOCKS[CUSTOM_BLOCK_BLUE] = {
    "name": "Blue Block",
    "texture": "blue_block.png",
    "solid": True,
    "hardness": 1.2,
    "drop_id": CUSTOM_BLOCK_BLUE,
    "falling": False,
}
```

## Typische Fehler

- Texture-Datei fehlt oder Name stimmt nicht.
- ID doppelt vergeben.
- hardness ist 0 oder negativ.
