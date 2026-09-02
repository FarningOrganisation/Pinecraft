# Tutorial: Neues Item

## Ziel

Du fuegst ein neues Item hinzu, das im Inventar auftaucht.

## Schritte

1. Neue Item-ID in src/ids.py vergeben (im STUDENT_ITEM_ID Bereich).
2. Item in src/items.py im ITEMS-Dictionary eintragen.
3. Texture in assets/textures/items ablegen.
4. Optional ein Crafting-Rezept in src/crafting_recipes.py ergaenzen.

## Minimalbeispiel

```python
# src/ids.py
CUSTOM_ITEM_CRYSTAL = STUDENT_ITEM_ID_START

# src/items.py
ITEMS[CUSTOM_ITEM_CRYSTAL] = {
    "item_id": CUSTOM_ITEM_CRYSTAL,
    "name": "Crystal",
    "texture": "crystal.png",
    "item_type": "material",
    "max_stack": 64,
}
```

## Typische Fehler

- item_id im Dict passt nicht zum Dictionary-Key.
- item_type ist ungueltig.
- max_stack <= 0.
