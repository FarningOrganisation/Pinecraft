"""Globale Konstanten für das erste Pinecraft-Milestone.

Diese Datei bleibt bewusst klein und verständlich für Anfängerinnen und
Anfänger. Später können hier z. B. Fenstergröße, Spielregeln oder
Konstanten für Blöcke ergänzt werden.
"""
import random

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
WINDOW_TITLE = "Pinecraft"
TARGET_FPS = 60
BACKGROUND_COLOR = (135, 206, 235, 255)  # Heller Himmelblau in RGBA

# TODO_STUDENT (⭐): Ändere den Seed und beobachte die Welt.
WORLD_SEED = random.randint(1,100000)

# TODO_STUDENT (⭐⭐⭐): Für Startmenü-Challenge auf True setzen oder zur Laufzeit umschalten.
START_FULLSCREEN = False

TILE_SIZE = 32
CHUNK_WIDTH = 48
WORLD_HEIGHT = 256

PLAYER_WIDTH = 28
PLAYER_HEIGHT = 64
PLAYER_SPEED = 220
PLAYER_JUMP_SPEED = 365
GRAVITY = 1400
GROUND_Y = 40
PLAYER_COLLISION_BOX_WIDTH = 28
PLAYER_COLLISION_BOX_HEIGHT = 64
PLAYER_START_X = SCREEN_WIDTH / 2
PLAYER_START_Y = GROUND_Y + PLAYER_HEIGHT / 2
