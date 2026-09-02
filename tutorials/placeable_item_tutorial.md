# Tutorial: Platzierbares Item

## Ziel

Du machst ein Item platzierbar (z. B. Schild, Deko, Pflanze).

## Schritte

1. Item normal in src/items.py anlegen.
2. place_as setzen (meist "item").
3. Optional placement_rules definieren.
4. Im Spiel mit Rechtsklick platzieren.

## Minimalbeispiel

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

## Typische Fehler

- place_as ist weder "item" noch "block".
- placement_rules ist kein dict.
- Support-Block-Liste hat ungueltige Werte.
