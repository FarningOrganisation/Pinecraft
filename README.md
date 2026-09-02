# Pinecraft

Pinecraft ist ein kleines 2D-Sandbox-Spiel mit Python und Arcade für den Unterricht.

Ziel: schnell starten, sofort etwas sehen, dann eigene Ideen einbauen.

## Schnellstart

### Voraussetzungen

- Python 3.12+
- Terminal

### Installation (macOS/Linux)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Installation (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Spiel starten

```bash
python main.py
```

### Entwicklung mit Auto-Restart

Wenn du nicht nach jeder Code-Aenderung neu starten willst:

```bash
python dev_hot_reload.py
```

Der Runner ueberwacht `main.py` und `src/**/*.py` und startet das Spiel
bei Aenderungen automatisch neu.

Hinweis: Der Spielcode liegt in `src/`, aber gestartet wird weiterhin bequem über `main.py` im Projekt-Root.

## Steuerung

- `A` / `D` oder Pfeiltasten links/rechts: laufen
- `W` / `SPACE` / Pfeil hoch: springen
- Linksklick: angreifen oder abbauen
- Rechtsklick: Block/Item platzieren
- `1` bis `9`: Hotbar-Slot wechseln
- `E`: Inventar/Crafting öffnen
- `P`: Test-Slime spawnen
- Bei Game Over: `ENTER` für Neustart

### Debug-Tasten (Lehrkraft)

- `Cmd + D`: Tageszeit auf Mittag
- `Cmd + N`: Tageszeit auf Mitternacht
- `Cmd + Links/Rechts`: Zeit schrittweise verändern

## Projektstruktur (bereinigt)

```text
pinecraft/
├── main.py               # Launcher
├── src/                  # gesamter Spielcode
├── assets/               # Texturen, Sounds, Fonts
├── PLAN.md
├── EXTENDING.md          # Student-Guide fuer eigene Erweiterungen
├── CHALLENGES.md         # Aufgaben mit Tutorial-Referenzen
├── tutorials/            # Schritt-fuer-Schritt-Tutorials
└── requirements.txt
```

Wichtig: Asset-Pfade sind jetzt zentral aufgebaut und funktionieren auch, wenn das Spiel aus einem anderen Arbeitsordner gestartet wird.

## Wo finde ich was?

- Spielschleife, Eingaben, Kamera, Draw: `src/game.py`
- Spieler (Bewegung, Angriff, Mining): `src/player.py`
- Mob-Basis: `src/mobs/mob.py`
- Monster-Basis: `src/mobs/monster.py`
- Boss-Basis: `src/mobs/boss_monster.py`
- Slime-Verhalten: `src/mobs/slime.py`
- Boss-Slime: `src/mobs/slime_boss.py`
- Mob-Templates: `src/mobs/mob_template.py`, `src/mobs/monster_template.py`, `src/mobs/boss_monster_template.py`
- Blockdaten und Blocktexturen: `src/blocks.py`
- Itemdaten und Itemtexturen: `src/items.py`
- Inventar- und Item-Helfer: `src/inventory.py`
- Hotbar und Inventar-UI: `src/ui/hotbar.py`, `src/ui/inventory_ui.py`
- Health-HUD: `src/ui/health_ui.py`
- Crafting-Rezepte: `src/crafting_recipes.py`
- Welt/Chunks: `src/world.py`, `src/world_generation.py`
- Licht/Tag-Nacht: `src/lighting.py`

## Tutorials

Direkte Schritt-fuer-Schritt-Anleitungen:

- [Block Tutorial](tutorials/block_tutorial.md)
- [Item Tutorial](tutorials/item_tutorial.md)
- [Placeable Item Tutorial](tutorials/placeable_item_tutorial.md)
- [Mob Tutorial](tutorials/mob_tutorial.md)
- [Monster Tutorial](tutorials/monster_tutorial.md)
- [Boss Tutorial](tutorials/boss_tutorial.md)
- [Biome/Worldgen Tutorial](tutorials/biome_worldgen_tutorial.md)

## Erweitern im Original-Code

Ihr sollt explizit in den Originalmodulen arbeiten und daraus lernen.

Empfohlener Einstieg:

1. `EXTENDING.md` lesen.
2. Passendes Tutorial waehlen.
3. Kleine Aenderung machen und direkt im Spiel testen.

## Challenges

Die Challenges liegen jetzt separat in [CHALLENGES.md](CHALLENGES.md) und
verweisen jeweils auf passende Tutorials.
