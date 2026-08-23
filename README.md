# Pinecraft

Dies ist die minimale erste Version von Pinecraft. Das Projekt wurde bewusst sehr klein gehalten, damit es für Programmieranfänger gut verständlich bleibt.

## Voraussetzungen

- Python 3.12 oder neuer
- ein Terminal oder eine Eingabeaufforderung

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Auf Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Starten

```bash
python main.py
```

## Inhalt der ersten Version

- Arcade-Fenster
- einfache Einstellungen in `settings.py`
- Update-Schleife und Draw-Schleife
- minimaler Startbildschirm

## Projektstruktur

```text
.
├── main.py
├── settings.py
├── requirements.txt
├── README.md
├── assets/
└── Pinecraft_PLAN.md
```

Diese Version enthält noch keine Spielfiguren, Welterzeugung, Inventar oder Gegner. Das kommt erst in späteren Milestones.
