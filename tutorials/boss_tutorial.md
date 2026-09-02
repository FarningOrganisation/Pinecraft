# Tutorial: Neuer Boss

## Ziel

Du baust einen Boss als Spezialisierung eines Monsters.

## Schritte

1. src/mobs/boss_monster_template.py kopieren.
2. @register_mob und Klasse umbenennen.
3. Schwierigkeit ueber HP, Schaden, Bewegung und Angriffsrhythmus einstellen.
4. Entscheiden, ob der Boss gespeichert werden soll (should_save).

## Hinweise

- Fuer unterbrechungsfreie Encounter kann should_save False liefern.
- Boss-Varianten mit Split-Mechanik koennen neue Mobs ueber pending_mob_spawns einreihen.
