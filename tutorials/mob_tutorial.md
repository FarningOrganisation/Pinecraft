# Tutorial: Neuer neutraler Mob

## Ziel

Du baust einen eigenen neutralen Mob.

## Schritte

1. src/mobs/mob_template.py kopieren (z. B. nach src/mobs/my_mob.py).
2. Klasse und Dateinamen umbenennen.
3. @register_mob mit eindeutiger MOB_TYPE setzen.
4. Animationen anpassen.
5. Optional save_state/load_state fuer eigene Felder.

## Wichtig

- Ohne @register_mob kann ein Mob nicht aus Save-Daten wiederhergestellt werden.
- Drops laufen ueber drop_table.

## Test-Tipp

In src/game.py DEBUG_SPAWN_MOB_CLASS auf deinen Mob setzen.
