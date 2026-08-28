# Pinecraft Lighting System Handoff

Dieses Dokument beschreibt den aktuellen Stand des Lichtsystems in der Codebasis.
Ziel: Es soll direkt an ein anderes LLM übergeben werden können.

## 1) Überblick

Das System kombiniert drei Ebenen:

1. Sky-Shader (GPU): zeichnet den Himmel mit Day/Night-Verlauf, Dämmerung und Cave-Tint.
2. LightLayer + Ambient (Arcade): mischt Szeneninhalt mit globaler Umgebungsfarbe.
3. CPU Depth Overlay (pro Tile): dunkelt unterirdische Bereiche blockbasiert ab.

Wichtig: Die aktuelle Block-Tiefenabdunklung ist nicht shaderbasiert, sondern CPU-basiert in einer Tile-Schleife.

## 2) Render-Reihenfolge

Datei: src/game.py, Methode on_draw

Ablauf im Frame:

1. clear
2. camera.use
3. with light_layer:
   - draw_sky_shader
   - draw_celestials
   - draw world sprites (chunks, items, mobs, player, water)
   - draw_underground_darkness_overlay
4. light_layer.draw(ambient_color=...)
5. UI zeichnen

Codeauszug:

    def on_draw(self):
        self.clear((0, 0, 0, 255))
        self.camera.use()

        with self.light_layer:
            self._draw_sky_shader()
            self.ui_camera.use()
            self._draw_celestials()
            self.camera.use()

            # world draw calls
            self.water_sprite_list.draw()
            self._draw_underground_darkness_overlay()

        self.light_layer.draw(ambient_color=self._ambient_color())

## 3) Sky-Shader

Datei: src/lighting.py

Der Sky-Shader nutzt drei Uniforms:

- u_day_factor
- u_time_of_day
- u_underground

u_underground kommt aus sky_background_blend().

Codeauszug:

    def draw_sky_shader(self):
        self.sky_shader_program["u_day_factor"] = float(self.day_factor())
        self.sky_shader_program["u_time_of_day"] = float(self.window.time_of_day)
        self.sky_shader_program["u_underground"] = float(self.sky_background_blend())
        self.sky_quad.render(self.sky_shader_program)

Shader-Idee:

- horizon/zenith Farben werden zwischen Tag/Nacht gemischt.
- cave_horizon/cave_zenith werden mit u_underground beigemischt.
- zusätzlich Twilight-Band für Sunrise/Sunset.

## 4) Ermittlung von Underground-Blending

Datei: src/lighting.py, Funktion sky_background_blend

Prinzip:

1. Um den Spieler wird ein Radius durchsucht.
2. Es wird nach Luftzellen gesucht, die über einer lichtblockierenden Top-Grenze liegen.
3. Die Distanz zur nächsten Open-Air-Zelle ergibt den Blend-Faktor.

Rückgabe:

- 0.0 nahe normalem Himmel
- 1.0 tief in Höhlen/ohne Open-Air-Verbindung

## 5) Depth Shadow der Blöcke (aktueller Mechanismus)

Datei: src/lighting.py, Funktion draw_underground_darkness_overlay

### 5.1 Pipeline

1. Sichtbaren Tile-Bereich bestimmen.
2. Basis-Tönung (braun/dunkel) über gesamten sichtbaren Bereich legen.
3. Torch-Positionen sammeln.
4. Connected Skylight in Luftzellen propagieren.
5. Für jede Spalte surface + shadow bonus berechnen.
6. Für jedes Tile effektive Tiefe per Nachbarsampling bestimmen.
7. Alpha aus Tiefe + Tagesfaktor ableiten.
8. Torch reduziert Alpha lokal.
9. Connected Skylight reduziert Alpha lokal.
10. Ambient-Rechteck + Dark-Rechteck pro Tile zeichnen.

### 5.2 Kernformeln

Effektive Tiefe aus Nachbarn:

    vertical_depth = max(0.0, (source_surface_y + 1) - sample_y)
    if vertical_depth > 0.0:
        vertical_depth += shadow_strength * (1.8 + shadow_depth_factor)

    lateral_penalty = (abs(dx) + abs(dy) * 0.7) * 1.4 * diagonal_weight
    effective_depth = vertical_depth + lateral_penalty
    min_effective_depth = min(min_effective_depth, effective_depth)

Alpha aus Tiefe:

    depth_after_threshold = max(0.0, (min_effective_depth - 0.7) * 1.35)
    alpha = int(min(255, (depth_after_threshold**1.18) * 14.5 * darkness_scale))
    alpha = int(alpha * daylight_alpha_scale)

Torch-Aufhellung:

    if dist <= 180.0:
        torch_boost = max(torch_boost, 1.0 - dist / 180.0)

    alpha = max(0, int(alpha * (1.0 - min(0.96, torch_boost * 1.1))))

Connected-Skylight-Abschwächung:

    connected_light = connected_sky_light.get((tile_x, tile_y), 0.0)
    alpha = int(alpha * max(0.0, 1.0 - min(0.98, connected_light * 0.98)))

Finales Dark-Overlay je Tile:

    dark_alpha = max(0, alpha - int(ambient_alpha * 0.7))
    if dark_alpha > 0:
        arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, (0, 0, 0, dark_alpha))

## 6) Relevante Abhängigkeiten

Datei: src/blocks.py

- get_block_light_opacity(block_id)
- is_block_skylight_surface(block_id)

Diese Funktionen steuern, welche Blöcke Licht blockieren und welche als natürliche Oberfläche für Skylight gelten.

## 7) Warum es blockig aussieht

Die Dunkelheitsmaske wird aktuell pro Tile als Rechteck gezeichnet.
Dadurch entstehen sichtbare Kanten und viele Draw-Calls.

## 8) Performance-Hotspots im aktuellen Depth-System

1. Viele world.get_block Aufrufe in verschachtelten Schleifen.
2. BFS für connected skylight im sichtbaren Bereich.
3. Pro Tile zusätzliche Torch-Distanzberechnung.
4. Viele arcade.draw_lrbt_rectangle_filled Calls.

## 9) Empfehlung für nächste Iteration

Falls ein anderes LLM das System verbessern soll, ist der sauberste nächste Schritt:

1. CPU berechnet nur ein grobes Depth/Light-Grid (z. B. 1 Wert pro 2x2 oder 4x4 Tiles).
2. Ein Fullscreen-Fragment-Shader sampelt/interpoliert dieses Grid weich.
3. Shader multipliziert nur auf Weltinhalt, nicht auf den Sky-Hintergrund.
4. Cave-Brown bleibt weiterhin über sky_background_blend steuerbar.

## 10) Quick Facts

- Sky ist bereits Shader-basiert.
- Depth-Shadow der Blöcke ist derzeit CPU-basiert.
- Celestials (Sonne/Mond) werden zusätzlich als Sprites gezeichnet.
- Fackeln beeinflussen sowohl LightLayer-Lights als auch Depth-Overlay-Aufhellung.
