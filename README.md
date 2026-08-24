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
├── Pinecraft_PLAN.md
└── requirements.txt
```

Wichtig: Asset-Pfade sind jetzt zentral aufgebaut und funktionieren auch, wenn das Spiel aus einem anderen Arbeitsordner gestartet wird.

## Wo finde ich was?

- Spielschleife, Eingaben, Kamera, Draw: `src/game.py`
- Spieler (Bewegung, Angriff, Mining): `src/player.py`
- Gegner-Basis: `src/enemies/enemy.py`
- Slime-Verhalten: `src/enemies/slime.py`
- Blockdaten und Blocktexturen: `src/blocks.py`
- Itemdaten und Itemtexturen: `src/items.py`
- Inventar- und Item-Helfer: `src/inventory.py`
- Hotbar und Inventar-UI: `src/ui/hotbar.py`, `src/ui/inventory_ui.py`
- Health-HUD: `src/ui/health_ui.py`
- Crafting-Rezepte: `src/crafting_recipes.py`
- Welt/Chunks: `src/world.py`, `src/world_generation.py`
- Licht/Tag-Nacht: `src/lighting.py`

## Challenges für Schüler:innen

Alle Aufgaben sind absichtlich als Einstiegspunkte formuliert. Ihr müsst nicht die komplette Engine verstehen.

### ⭐ Challenge 1: Seed im Code ändern und Welt vergleichen

Ziel:

1. Seed-Wert im Code anpassen.
2. Spiel neu starten.
3. Beobachten, wie sich die Weltform verändert.

Einstiegspunkt:

- `src/world.py` (Konstruktor mit `seed`)
- optional `src/world_generation.py` (wie der Seed die Höhen/Caves beeinflusst)

Hinweis:

- Fangt mit kleinen Schritten an, z. B. `1337` -> `1338`.

### ⭐ Challenge 2: Spiel starten und Pickaxe craften

Ziel:

1. Spiel starten.
2. Inventar mit `E` oeffnen.
3. Material in das 3x3-Crafting legen.
4. Eine Pickaxe craften.

Einstiegspunkt:

- `src/crafting_recipes.py` (Rezeptaufbau verstehen)
- `src/ui/inventory_ui.py` (Crafting-Logik im UI)

Hinweis:

- Das Pickaxe-Rezept ist bereits enthalten. Diese Challenge ist zum Verstehen des Systems.

### ⭐⭐ Challenge 3: Sand-Block implementieren oder erweitern

Idee:

- Neuen Sand-Block fertig einbauen (falls noch nicht komplett), oder Sand fallen lassen, wenn darunter Luft ist.

Einstiegspunkt:

- `src/blocks.py` (Blockdefinition)
- `src/world.py` oder `src/physics.py` (Verhalten)

Hinweis:

- Startet einfach mit Blockdaten, danach Verhalten.

### ⭐⭐ Challenge 4: Tree Seeds als seltener Drop bei Holz

Idee:

- Beim Abbau von Baumstamm soll mit kleiner Chance ein Seed-Item droppen.

Einstiegspunkt:

- `src/items.py` (neues Item anlegen)
- `src/player.py` (Drop-Logik nach Mining)
- optional `src/blocks.py` (welcher Block als "Holz" gilt)

Hinweis:

- Erst mit fixer Chance starten, z. B. 5 Prozent.

### ⭐ Challenge 5: Sword-Crafting-Rezept

Idee:

- Rezept für Schwert in das 3x3-Crafting aufnehmen.

Einstiegspunkt:

- `src/crafting_recipes.py`
- `src/items.py` (falls neues Schwert-Item nötig)

Hinweis:

- Muster als 3x3-Grid in `CRAFTING_RECIPES` eintragen.

### ⭐⭐⭐ Challenge 6: Startmenü mit Seed-Eingabe + Fullscreen-Option

Idee:

- Vor dem Spiel ein kleines Menü anzeigen:
- Seed eintippen
- Fullscreen ein/aus
- dann auf "Play" starten

Einstiegspunkt:

- `src/game.py` (Fensterzustand, Eingaben, Startflow)
- `src/world.py` (Seed an World uebergeben)
- `src/settings.py` (Default-Werte, falls gewünscht)

Hinweis:

- Erst nur Seed-Auswahl bauen, danach Fullscreen als zweiter Schritt.

### ⭐⭐⭐ Challenge 7: BabySlime beim Tod eines grossen Slimes

Idee:

- Wenn ein großer Slime stirbt, spawnen drei BabySlimes.

Einstiegspunkt:

- `src/enemies/slime.py` (Slime-Subklasse, Spawn-Parameter)
- `src/enemies/enemy.py` (Death-Hook `on_death`)
- `src/game.py` oder `src/enemies/enemy_spawning.py` (Spawn-Integration)

Hinweis:

- Erst einen kleineren Slime mit weniger HP bauen, dann Spawn beim Tod triggern.

### ⭐⭐⭐ Challenge 8: Weitere Pickaxe-Rezepte

Idee:

- Iron Pickaxe, Gold Pickaxe, Diamond Pickaxe als craftbare Tools.

Einstiegspunkt:

- `src/items.py` (neue Item-Definitionen)
- `src/crafting_recipes.py` (Rezepte)
- `src/inventory.py` (optional Toolwerte wie Mining-Speed)

Hinweis:

- Erst die Items sichtbar machen, dann Werte wie `mining_speed` feinjustieren.

### ⭐ Challenge 9: Hintergrundmusik beim Spielen

Idee:

- Beim Starten des Spiels soll Musik im Hintergrund laufen.

Einstiegspunkt:

- `src/game.py` (Initialisierung, Setup, Spielstart)

Hinweis:

- Nutzt eine Datei aus `assets/sounds/`.
- Startet zunächst mit einer Schleife (Loop), Lautstärke später feinjustieren.

### ⭐⭐ Challenge 10: Soundeffekte für Mining und Angriff

Idee:

- Beim Abbauen eines Blocks und beim Angriff sollen kurze Soundeffekte abgespielt werden.

Einstiegspunkt:

- `src/player.py` (`start_mining`, `release_mining_result`, `start_attack`)
- `src/game.py` (Input-Pfade in `on_mouse_press`)

Hinweis:

- Erst einfache One-Shot-Sounds abspielen.
- Danach optional unterscheiden: Treffer-Sound vs. Fehlschlag-Sound.

### ⭐⭐⭐ Challenge 11: Hurt-Animation + Knockback für den Spieler

Idee:

- Wenn der Spieler Schaden bekommt, soll er eine kurze Hurt-Animation zeigen und zurückgestoßen werden.

Einstiegspunkt:

- `src/enemies/enemy.py` (`handle_contact_damage`)
- `src/player.py` (neuer Hurt-Zustand, Timer, visuelles Feedback)
- `src/physics.py` (Rückstoß sauber mit Kollisionen zusammenspielen lassen)

Hinweis:

- Startet mit kleinem Knockback und kurzer Unverwundbarkeitszeit.
- Achtet darauf, dass der Spieler nach der Hurt-Phase wieder normal steuerbar ist.

## Unterrichtsmodus: schnell erweitern

Empfohlene Reihenfolge im Unterricht:

1. Starten und kurz spielen.
2. Eine ⭐ Aufgabe in 15-20 Minuten.
3. Danach eine ⭐⭐ oder ⭐⭐⭐ Aufgabe in Teams.

So bekommen alle schnell Erfolgserlebnisse und trotzdem spannende Vertiefung.
