# Tutorial: Neuer Monster-Mob

## Ziel

Du baust einen aggressiven Gegner mit Chase/Attack-Verhalten.

## Schritte

1. src/mobs/monster_template.py kopieren.
2. @register_mob und Klasse umbenennen.
3. Werte wie speed, damage, activate_range einstellen.
4. Optional _update_attack_behavior fuer Spezialangriffe ueberschreiben.

## Hooks

- _update_alerted_behavior(player, delta_time)
- _update_attack_behavior(player, delta_time)
- save_state/load_state

## Test-Tipp

Zuerst nur Lauf/Schaden testen, danach Spezialverhalten einbauen.
