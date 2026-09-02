# Tutorial: Biome und World Generation tunen

## Ziel

Du veraenderst das Aussehen der Welt ueber Parameter statt Core-Algorithmen.

## Dateien

- src/world_gen_config.py
- src/world_generation.py

## Wichtige Regler in world_gen_config.py

- biomes (Liste aus BiomeDefinition)
- weight pro Biome (wird intern normalisiert)
- is_ocean fuer Ocean-Biome
- surface_block_id, subsurface_block_id, deep_block_id pro Biome
- cave_density_multiplier
- cave_pocket_signal_threshold, cave_pocket_chamber_threshold
- ore_density_multiplier
- sea_level

## Vorgehen

1. Einen Regler aendern.
2. Spiel starten und Welt testen.
3. Naechsten Regler anpassen.

## Beispiele

- Hoehere Ocean-Wahrscheinlichkeit: beim Biome "ocean" weight erhoehen.
- Snow-Biome vorbereiten: neues Biome mit eigenen surface/subsurface/deep Block-IDs.
- Mehr Hoehlen: cave_density_multiplier von 1.0 auf 1.15.
- Weniger Erze: ore_density_multiplier von 1.0 auf 0.8.
- Gebirgiger: im Mountain-Biome profile.terrain_amp erhoehen.

## Typische Fehler

- Alle Biome-Gewichte sind 0.
- Ocean-Biome fehlt (is_ocean=True).
- Dichte-Multiplikatoren <= 0.
- Extreme Werte fuehren zu unspielbarem Terrain.

Beim Start gibt es dafuer direkte [worldgen][hint]-Meldungen.
