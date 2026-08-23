# PLAN.md — Pinecraft

## 1. Project Goal

Build a small, intentionally simple **2D Minecraft-inspired sandbox game** using **Python + Arcade**.

The project is called **Pinecraft** — a name combining the Python/Py idea with the mining-and-crafting inspiration of the game.

The project is designed for children and teenagers in a programming school. It should be fun to play, easy to understand, and especially easy to extend during holiday programming lessons.

This is **not** intended to become a complete Minecraft clone.

The priorities are:

1. Easy to run.
2. Easy to understand.
3. Immediate visual feedback.
4. Simple architecture.
5. Many obvious extension points for students.
6. Completely free development tools and assets.
7. Suitable for pair programming and classroom use.

The initial version should feel like a small playable game while deliberately leaving many features for students to implement.

---

# 2. Technology

Use:

- Python 3.12+ where practical
- Arcade
- Standard Python library whenever possible

Avoid unnecessary dependencies.

Development environment:

- Visual Studio Code
- Git
- GitHub
- GitHub Copilot

The project should run with:

```bash
python main.py
```

---

# 3. Target Audience

The game will be used by students with different skill levels.

Approximate range:

- beginners who know variables, if-statements, loops, and functions
- intermediate students who know lists and classes
- advanced students who can work with algorithms, inheritance, procedural generation, and game AI

Because of this, the codebase should provide tasks at multiple difficulty levels.

Do not make the architecture unnecessarily abstract.

Prefer readable code over clever code.

---

# 4. Core Design

The game is a **2D side-view block world**.

Think of:

- Minecraft
- Terraria
- a simple platformer

The player can:

- walk left and right
- jump
- collide with blocks
- break blocks
- place blocks
- select blocks/items from a hotbar
- explore a procedurally generated world

The first version should contain only a small number of systems.

Do not implement everything at once.

---

# 5. Minimal Playable Version

The first classroom-ready release should already feel like a small real game.

It should include:

- an effectively infinite horizontal world
- chunk-based procedural world generation
- grass, dirt, stone, and caves
- player movement, gravity, jumping, and collision
- camera scrolling
- block breaking and placement
- simple hotbar and inventory counts
- one simple enemy
- player health and game-over behavior
- a continuous day/night cycle
- smooth sky/background changes
- ambient darkness underground
- placeable torches or another local light source
- GPU/shader-based lighting where practical

The base game may therefore contain slightly more engine sophistication than a typical beginner teaching project. This is intentional: students should receive something that already feels interesting and atmospheric.

The student-facing APIs and extension points must still remain simple.

# 6. Project Structure

Keep the number of files reasonably small.

Suggested structure:

```text
pinecraft/
│
├── main.py
├── game.py
├── settings.py
│
├── world/
│   ├── world.py
│   ├── chunks.py
│   ├── generation.py
│   └── blocks.py
│
├── entities/
│   ├── player.py
│   └── enemies.py
│
├── systems/
│   ├── inventory.py
│   ├── lighting.py
│   └── crafting.py
│
├── shaders/
│   ├── world_lighting.glsl
│   └── README.md
│
├── assets/
│   ├── textures/
│   ├── sounds/
│   └── fonts/
│
├── tests/
│
├── README.md
└── PLAN.md
```

This structure is a guideline.

Do not split very small modules into many tiny files just for architectural purity.

---

# 7. World Representation

The world should be **effectively infinite horizontally**.

Do not allocate one gigantic 2D array. Divide the world into chunks.

Example:

```python
CHUNK_WIDTH = 32
WORLD_HEIGHT = 128
LOAD_RADIUS = 3
UNLOAD_RADIUS = 5
```

A chunk can conceptually contain:

```python
chunk.blocks[y][local_x]
```

The `World` object manages loaded chunks. Students should normally interact through a simple API:

```python
world.get_block(x, y)
world.set_block(x, y, block_id)
world.is_solid(x, y)
world.break_block(x, y)
world.place_block(x, y, block_id)
```

Chunk coordinates should be calculated centrally:

```python
chunk_x = world_x // CHUNK_WIDTH
local_x = world_x % CHUNK_WIDTH
```

Negative world coordinates must work.

## Loaded Chunk Window

Only keep chunks near the player active.

```text
unloaded | loaded | loaded | PLAYER | loaded | loaded | unloaded
```

When the player approaches the edge of the loaded area:

1. determine which chunks are needed,
2. generate missing chunks,
3. create their render data,
4. unload chunks far away.

This lets the player keep walking in either direction without a predefined world width.

## Deterministic Generation

Chunk generation must be deterministic.

Given the same:

```python
world_seed
chunk_x
```

the generated chunk must always be identical.

Do not use one global random sequence whose result depends on chunk-loading order. Derive randomness from the world seed and chunk coordinate.

## Modified Chunks

Generated terrain does not need to remain permanently stored. Only player changes need to be remembered later, for example:

- mined blocks
- placed blocks
- torches
- chests

A future save system can persist these modifications separately from generated terrain.

# 8. Block Definitions

Blocks should be mostly data-driven.

Example:

```python
BLOCKS = {
    GRASS: {
        "name": "Grass",
        "texture": "grass.png",
        "solid": True,
        "hardness": 1,
    },
    STONE: {
        "name": "Stone",
        "texture": "stone.png",
        "solid": True,
        "hardness": 3,
    },
}
```

Students should be able to add a new block by changing only a small amount of code.

Possible later properties:

- hardness
- tool requirement
- light emission
- damage
- gravity
- drops
- transparency
- animation
- sound
- crafting behavior

Do not implement all of these in the first version.

---

# 9. Coordinate System

Clearly distinguish between:

- world grid coordinates
- pixel coordinates
- screen coordinates

Create helper functions such as:

```python
grid_to_pixel(x, y)
pixel_to_grid(px, py)
```

Use a constant such as:

```python
TILE_SIZE = 32
```

Keep coordinate conversion centralized.

Avoid duplicating coordinate math throughout the project.

---

# 10. Player

The player should initially support:

- left/right movement
- gravity
- jumping
- block collision
- health
- interaction range

Keep the player's logic readable.

Possible player fields:

```python
health
max_health
speed
jump_speed
selected_hotbar_slot
interaction_range
```

Avoid implementing hunger, armor, experience, status effects, etc. in the base version.

Those are excellent student extensions.

---

# 11. Physics

Use simple platformer physics.

Requirements:

- gravity
- horizontal collision
- vertical collision
- jumping only when standing on ground

Prefer Arcade's existing physics helpers if they keep the implementation understandable.

Do not build a complex physics engine.

---

# 12. Camera

The camera should follow the player horizontally and vertically.

Movement should feel smooth but does not need to be sophisticated.

Students should not need to understand camera internals to implement most tasks.

---

# 13. Breaking Blocks

Basic behavior:

1. Student/player points at a block.
2. Game converts mouse position to world coordinates.
3. Check interaction range.
4. Check whether block can be broken.
5. Remove block.
6. Add corresponding item to inventory.

Initially, block breaking may happen instantly.

Later student tasks can introduce:

- hardness
- mining time
- tools
- animations
- particles
- sounds

---

# 14. Placing Blocks

Basic behavior:

1. Choose a block from hotbar.
2. Right-click a valid empty grid location.
3. Check interaction range.
4. Do not allow block placement inside the player.
5. Remove one item from inventory.
6. Place block.

---

# 15. Inventory

Keep the initial inventory extremely small.

Recommended:

```python
inventory = {
    GRASS: 10,
    DIRT: 20,
    STONE: 5,
}
```

A hotbar can contain a small ordered list:

```python
hotbar = [
    GRASS,
    DIRT,
    STONE,
]
```

Do not build a large Minecraft-style inventory UI in the first version.

---

# 16. Procedural Terrain

Terrain generation must work **per chunk** so the world can continue generating as the player explores.

The generator should initially create:

- a smooth surface height
- grass at the surface
- dirt below grass
- stone deeper underground
- underground empty spaces/caves

Generation must be seamless across chunk boundaries and deterministic from the world seed.

Suggested API:

```python
chunk = generate_chunk(
    seed=world.seed,
    chunk_x=chunk_x,
)
```

Avoid requiring neighboring chunks to already exist.

Later additions may include:

- ores
- trees
- biome regions
- lakes
- structures

---

# 16A. Infinite World / Chunk Streaming

Infinite exploration is a **core engine feature**, not merely a student exercise.

The world is only logically infinite. At any moment, keep a limited area around the player in memory.

Suggested configuration:

```python
LOAD_RADIUS = 3
UNLOAD_RADIUS = 5
```

Requirements:

- generate nearby missing chunks as the player moves
- load them before they visibly pop in where practical
- unload distant chunks
- render only nearby chunks
- do not fully simulate entities in unloaded chunks
- support positive and negative world coordinates
- do not define a fixed `WORLD_WIDTH`

Do not introduce threads or async generation unless performance testing proves they are necessary. Prefer a simple synchronous implementation first.

---

# 16B. Day and Night Cycle

A day/night cycle is a **core visual feature**.

Maintain normalized world time:

```python
time_of_day = 0.0
```

Suggested convention:

```text
0.00 = midnight
0.25 = sunrise
0.50 = noon
0.75 = sunset
1.00 = midnight
```

The value loops continuously.

Example:

```python
DAY_LENGTH_SECONDS = 300
```

The cycle controls:

- sky/background color
- global ambient brightness
- optional sun, moon, and stars
- optional enemy behavior

Expose simple helpers:

```python
get_ambient_light(time_of_day)
is_night(time_of_day)
```

Transitions should be smooth.

---

# 16C. Lighting and Underground Darkness

Lighting is part of the base game's atmosphere.

Desired behavior:

- daytime surface is bright
- nighttime surface is dark
- underground is dark even during daytime
- torches create local circles of light
- caves are difficult to explore without light

Do **not** attempt physically accurate Minecraft-style light propagation for the first version.

## Recommended Rendering Model

Render the world normally, then apply a lighting pass:

```text
world render
    +
ambient darkness
    +
local lights
    =
final image
```

Use Arcade's OpenGL/shader support where practical.

Keep shader code isolated from ordinary gameplay code. Students adding blocks, enemies, crafting recipes, etc. should not need to understand GLSL.

## Ambient Light

Ambient light depends on:

1. time of day
2. whether an area is exposed to the sky or underground

At noon:

```text
surface     -> bright
underground -> dark
```

At midnight:

```text
surface     -> dark
underground -> very dark
```

Use a simple approximation instead of expensive full-world light propagation.

## Torches

Torches should be placeable and emit local light.

Suggested properties:

```python
light_radius
light_strength
```

Example:

```python
TORCH_LIGHT_RADIUS = 180
```

Multiple nearby lights may overlap.

Later light-emitting objects may include:

- lava
- glowing ore
- campfires
- magic crystals
- enemies
- projectiles

## Underground Detection

Keep underground darkness simple.

Possible approaches:

- determine whether a tile has open sky above it
- maintain lightweight sunlight values per column/tile
- approximate underground darkness based on solid blocks above

Do not calculate expensive lighting for the whole explored world every frame. Lighting should concern only the visible or nearby area.

## Shader Scope

Shaders may be used for:

- global darkness tint
- smooth day/night transitions
- torch light falloff
- glow
- subtle vignette
- optional color grading
- optional torch flicker

Shaders should **not** become mandatory knowledge for ordinary student tasks.

Keep GLSL files in `shaders/` and comment them clearly.

Advanced students may later receive optional shader exercises.

# 17. Enemy System

The base game should contain exactly one very simple enemy type.

Recommended enemy:

## Slime

Behavior:

- moves slowly toward the player
- periodically jumps
- hurts the player on contact
- has a small amount of health

Keep enemy logic simple.

Suggested structure:

```python
class Enemy:
    ...

class Slime(Enemy):
    ...
```

Do not create a large inheritance hierarchy.

More enemy types should be student projects.

---

# 18. Combat

Combat in the base version should be minimal.

Possible first behavior:

- press or click to attack
- enemies inside a short range take damage
- enemy disappears at 0 health

No complicated combat system is required initially.

Later extensions:

- swords
- attack cooldown
- knockback
- bows
- projectiles
- armor
- critical hits

---

# 19. Game State

Support only a few states initially:

- playing
- game over

Optional later states:

- title screen
- pause menu
- inventory
- crafting
- world selection

Keep state transitions simple and explicit.

---

# 20. Rendering

Use simple original pixel-art-style assets.

Requirements:

- no copyrighted Minecraft textures
- no ripped Minecraft assets
- assets should be original, public domain, CC0, or created specifically for this project

Placeholder textures may initially be simple colored squares.

The game should work even before polished assets exist.

---

# 21. Asset Philosophy

Gameplay and teaching value are more important than graphics.

Do not spend excessive development time on art.

For the initial implementation:

- 16x16 or 32x32 pixel textures
- simple shapes
- obvious visual differences between blocks

Possible blocks:

- grass
- dirt
- stone
- wood
- leaves
- coal ore

Possible character art:

- simple explorer
- slime

---

# 22. Coding Style

The code is educational.

Therefore:

## Prefer

```python
if player.health <= 0:
    game_over()
```

over highly abstract solutions.

Prefer:

- descriptive variable names
- small functions
- type hints where they aid understanding
- docstrings for important systems
- comments explaining non-obvious game logic

Avoid:

- unnecessary metaprogramming
- decorators unless clearly useful
- complex design patterns
- dependency injection frameworks
- deep inheritance
- premature optimization
- clever one-liners

---

# 23. Language

Source-code identifiers should generally be English because students will encounter English programming terminology elsewhere.

Examples:

```python
player
world
block
enemy
inventory
```

Student-facing explanations and exercise comments may be in German.

Example:

```python
# AUFGABE:
# Der Schleim soll dem Spieler folgen.
#
# Tipp:
# Vergleiche die x-Position des Schleims mit
# der x-Position des Spielers.
```

German umlauts may be used normally in comments and documentation.

---

# 24. Student Task Markers

Use consistent markers for student exercises.

Example:

```python
# ============================================================
# AUFGABE 07 — Schleim-KI
#
# Der Schleim soll sich in Richtung des Spielers bewegen.
#
# Anforderungen:
# - Spieler links -> Schleim läuft nach links
# - Spieler rechts -> Schleim läuft nach rechts
#
# BONUS:
# Der Schleim bleibt stehen, wenn der Spieler zu weit entfernt ist.
# ============================================================
```

Use `TODO_STUDENT` for code locations intended for modification.

Example:

```python
# TODO_STUDENT: Implementiere hier die Bewegung des Schleims.
```

Do not leave essential engine functionality broken unless the corresponding lesson explicitly asks students to implement it.

---

# 25. Difficulty Levels

Student exercises should be marked:

- ⭐ Beginner
- ⭐⭐ Intermediate
- ⭐⭐⭐ Advanced

Beginner tasks should require small local changes.

Intermediate tasks may involve multiple functions or files.

Advanced tasks may require designing new systems.

---

# 26. Suggested Student Projects

## ⭐ Beginner

### Task 1 — New Block

Add a new block type.

Ideas:

- sand
- bricks
- glass
- gold
- chocolate

Learn:

- constants
- dictionaries
- game data

---

### Task 2 — Faster Player

Add a sprint button.

Learn:

- keyboard input
- conditions
- variables

---

### Task 3 — Super Jump

Create a special block that makes the player jump higher.

Learn:

- collision
- conditions

---

### Task 4 — Dangerous Block

Create lava or spikes.

Touching the block reduces player health.

Learn:

- conditions
- health

---

### Task 5 — New Enemy Texture

Create a visually different enemy.

Learn:

- assets
- classes
- configuration

---

# 27. Intermediate Student Projects

## ⭐⭐ Intermediate

### Task 6 — Zombie

Implement a zombie enemy.

Requirements:

- walks toward the player
- deals damage
- has health

---

### Task 7 — Block Hardness

Different blocks require different amounts of time to mine.

Example:

```text
Dirt  -> fast
Stone -> medium
Ore   -> slow
```

---

### Task 8 — Tools

Add:

- wooden pickaxe
- stone pickaxe

Tools should affect mining speed.

---

### Task 9 — Trees

Generate simple trees during world generation.

---

### Task 10 — Ores

Generate coal and iron below certain depths.

---

### Task 11 — Falling Sand

Sand should fall if there is air underneath it.

---

### Task 12 — Simple Crafting

Example:

```text
2 Wood -> 4 Planks
3 Stone -> Stone Pickaxe
```

---

# 28. Advanced Student Projects

## ⭐⭐⭐ Advanced

### Task 13 — Cave Generation

Generate underground cave systems.

Possible approaches:

- random walk
- cellular automata
- noise

---

### Task 14 — Biomes

Add different terrain regions.

Examples:

- forest
- desert
- snow
- rocky mountains

---

### Task 15 — Better Enemy AI

Enemies should:

- detect player
- chase player
- stop when blocked
- jump over small obstacles

---

### Task 16 — Save and Load

Save the world to a file.

Possible format:

- JSON

Save:

- seed
- changed blocks
- player position
- inventory
- health

---

### Task 17 — Day/Night Cycle

Create a changing background and enemy behavior.

---

### Task 18 — Boss Enemy

Create a boss with multiple attack patterns.

---

### Task 19 — Procedural Structures

Generate:

- houses
- ruins
- caves
- treasure rooms

---

### Task 20 — Multiplayer

Only attempt this if the rest of the project is stable.

Networking is explicitly outside the scope of the base game.

---

# 29. Verification Strategy

Do not use pytest or require students to learn an automated testing framework for this project.

The main feedback loop is:

```text
change code -> run game -> see what changed
```

That is intentional.

For engine development, prefer built-in debug tools and sanity checks.

Useful debug options:

- player world coordinates
- current chunk coordinate
- loaded chunk count
- FPS
- current time of day
- hitbox display
- chunk-boundary display
- lighting debug view
- regenerate the world from the same seed

Pure helper functions may use occasional simple `assert` statements during teacher development if useful, but these should not become part of the student workflow.

# 30. Git Strategy for Classroom Use

Create a stable teacher branch:

```text
main
```

Possible student branches:

```text
student/zombie
student/crafting
student/trees
```

For pair programming, two students may work on one feature branch.

Commit messages should be simple and meaningful.

Examples:

```text
Add slime movement
Add coal block
Fix player collision
Implement tree generation
```

---

# 31. Classroom Safety

The game should fail gracefully.

Avoid features that can easily freeze the computer.

Especially protect against:

- infinite chunk-generation loops
- spawning millions of sprites
- accidentally retaining all explored chunks forever
- recursion without limits
- modifying lists while iterating incorrectly
- loading missing textures without useful error messages

Use reasonable constants.

Example:

```python
CHUNK_WIDTH = 32
WORLD_HEIGHT = 128
LOAD_RADIUS = 3
UNLOAD_RADIUS = 5
```

These values may be adjusted after performance testing.

---

# 32. Performance Guidelines

Do not optimize prematurely.

However:

- never render every explored chunk every frame
- only draw blocks near the camera
- avoid creating unnecessary sprites
- never scan the complete explored world every frame
- unload distant chunk render data
- update lighting only for the visible/nearby area
- enemy logic should only run for nearby/active enemies where practical

If a simple solution performs well enough for classroom machines, prefer it.

---

# 33. Definition of Done — Base Version

The base project is ready for classroom use when:

- [ ] installation works from a fresh clone
- [ ] game starts with `python main.py`
- [ ] player can move and jump
- [ ] collision works
- [ ] camera follows player
- [ ] world is chunk-based
- [ ] player can explore indefinitely in both horizontal directions
- [ ] chunks generate deterministically from a world seed
- [ ] distant chunks unload correctly
- [ ] chunk borders do not create obvious terrain seams
- [ ] grass/dirt/stone and caves exist
- [ ] blocks can be broken and placed
- [ ] broken blocks enter inventory
- [ ] hotbar selection works
- [ ] day/night cycle works
- [ ] sunrise and sunset transition smoothly
- [ ] underground areas are dark
- [ ] torches create local light
- [ ] lighting performs acceptably on classroom PCs
- [ ] one simple slime enemy exists
- [ ] player and enemy can take damage
- [ ] game-over condition exists
- [ ] debug view can show chunk/FPS/lighting information
- [ ] code contains clear extension points
- [ ] README explains setup
- [ ] student tasks are documented
- [ ] game runs reliably on classroom PCs

# 34. Development Milestones

## Milestone 1 — Empty Arcade Game

Create the Arcade window, settings, update loop, and draw loop.

---

## Milestone 2 — Player

Implement player sprite, movement, gravity, and jumping.

---

## Milestone 3 — Block and Chunk Data Model

Implement:

- block IDs
- chunk class
- world/chunk coordinate conversion
- `get_block()` / `set_block()`
- negative chunk coordinates

---

## Milestone 4 — Static Generated Chunks

Generate several chunks around spawn with deterministic grass, dirt, and stone.

Verify chunk edges join seamlessly.

---

## Milestone 5 — Collision and Camera

Implement solid-block collision, camera following, and visible-chunk rendering.

---

## Milestone 6 — Infinite Chunk Streaming

Implement:

- current-player-chunk detection
- generation of nearby missing chunks
- preloading near the camera
- unloading distant chunks
- debug display for loaded chunks

After this milestone the player should be able to keep walking indefinitely.

---

## Milestone 7 — Mining

Implement mouse-to-grid conversion, interaction range, block breaking, and inventory gain.

---

## Milestone 8 — Block Placement and Hotbar

Implement hotbar, inventory consumption, and valid placement checks.

---

## Milestone 9 — Caves

Add deterministic underground spaces that remain seamless across chunk boundaries.

---

## Milestone 10 — Day/Night Cycle

Implement normalized world time, sky/background transition, and global ambient brightness.

---

## Milestone 11 — Lighting Render Pass

Implement the visual lighting foundation:

- world render target where needed
- ambient darkness
- day/night brightness integration
- isolated shader code

Start with the simplest reliable shader solution.

---

## Milestone 12 — Underground Darkness and Torches

Implement:

- darkness underground
- placeable torches
- local radial/point light
- overlapping lights
- acceptable performance with multiple torches

The goal is atmosphere, not physically accurate global illumination.

---

## Milestone 13 — Enemy

Implement the basic slime.

---

## Milestone 14 — Health and Combat

Implement player health, enemy health, damage, and game over.

---

## Milestone 15 — Classroom Cleanup

Add:

- German exercise comments
- `TODO_STUDENT` markers
- README
- debug controls
- clear error messages
- starter extension tasks

Ordinary student tasks should not require understanding chunk internals or GLSL.

---

## Milestone 16 — Multiplayer Architecture

Introduce the first networking layer for a local multiplayer prototype.

This is not yet a full online game service. The goal is a simple, understandable architecture that students can extend later.

Important prerequisite:

- mining and block placement already exist in the local single-player game
- the multiplayer layer is added afterwards as a networked extension of those mechanics

Implement:

- a dedicated server process for a world instance
- a client process for each player
- one server-authoritative world state
- client-to-server input messages for movement, jump, and interaction
- server-to-client state updates for the player and nearby world data
- a simple player list that represents remote players on the client

Important rule:

- The server owns the world simulation.
- Clients do not decide their own final position.
- Clients send input events, not trusted world state.

This keeps movement consistent and avoids desync.

---

## Milestone 17 — Remote Player Simulation

Add support for other players that live in the world but are not controlled locally.

Implement:

- player entity IDs
- position and velocity snapshots from the server
- interpolation or smoothing on the client for remote players
- local player rendering and remote player rendering as separate concepts
- a simple lobby or world join flow for connecting to another server

The client should render remote players as simulated actors whose state comes from the server, not from local input.

---

## Milestone 18 — Server Hosting and Join Flow

Add the first practical network UX.

Implement:

- host a world from the game automatically or via a menu option
- join a server by IP/hostname and port
- connection status, ping, and reconnect handling
- world chunk requests or nearby-world sync for new clients
- server-side validation of movement, collisions, and actions

At this stage, a game may still run as both a local single-player world and a network host, but the underlying logic should already be built around a server-authoritative model.

---

## Milestone 19 — Block Edit Sync and World Replication

This milestone adds the network version of the normal block editing system.

The local game must already support:

- mining blocks
- placing blocks
- inventory updates
- interaction range and block validation

Then the multiplayer layer synchronizes those changes across clients:

- the client sends a mine/place action request to the server
- the server validates the action against the world state
- the server updates the world
- the server broadcasts the changed block data to all connected clients
- all clients apply the same block change locally

Also implement:

- player input packets from client to server
- tick-based simulation on the server
- compressed state updates or delta updates for world changes
- chunk/world sync for clients entering the world or moving across loaded areas
- a clear distinction between simulation state and render state
- client-side prediction only as a later optional optimization

The goal is not a fully featured MMO. The goal is a clear, teachable multiplayer architecture that still matches the educational style of the project.

---

# 35. README Requirements

README.md should explain:

## Installation

Recommended:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Then:

```bash
pip install -r requirements.txt
```

Run:

```bash
python main.py
```

README should also explain:

- controls
- project structure
- how to add a block
- how to add an enemy
- how chunk loading works at a high level
- how day/night and lighting work at a high level
- how student exercises work

the README should be in German language

---

# 36. Pair Programming

Holiday lessons may use pair programming.

Recommended roles:

## Driver

- controls keyboard and mouse
- writes code
- explains what they are doing

## Navigator

- thinks about the solution
- checks for mistakes
- reads documentation
- suggests the next step

Students switch roles after every task or after approximately 10–15 minutes.

Both students should discuss changes before asking Copilot for a full solution.

---

# 37. Copilot Rules

GitHub Copilot is allowed to assist development, but the codebase should remain understandable to students.

When generating code, Copilot should follow these rules.

## Rule 1

Do not over-engineer.

Use the simplest implementation that satisfies the current milestone.

## Rule 2

Do not add unrelated features.

If asked to implement block placement, do not also introduce crafting, tools, or saving.

## Rule 3

Preserve student TODO sections.

Do not automatically implement code marked:

```python
TODO_STUDENT
```

unless explicitly asked to do so.

## Rule 4

Prefer small changes.

Do not rewrite large parts of the project unless necessary.

## Rule 5

Explain architectural changes.

Before making a significant structural change, describe:

- why it is needed
- which files are affected
- whether it makes student tasks harder

## Rule 6

Keep APIs simple.

A student should be able to understand calls such as:

```python
world.get_block(x, y)
world.set_block(x, y, STONE)
player.take_damage(1)
inventory.add(DIRT, 1)
```

## Rule 7

Do not use copyrighted Minecraft assets.

Use original placeholders.

## Rule 8

Do not silently introduce new dependencies.

If a dependency is needed, explain why first.

## Rule 9

When fixing bugs, prefer fixing the root cause rather than adding defensive hacks.

## Rule 10

Do not introduce pytest or another testing framework unless explicitly requested. Prefer visual verification, debug information, and simple sanity checks.

---

# 38. Copilot Implementation Workflow

When asked to implement a feature, use this workflow:

1. Read `PLAN.md`.
2. Inspect the existing relevant files.
3. Identify the smallest reasonable change.
4. Explain the intended change briefly.
5. Implement it.
6. Run relevant tests.
7. Fix failures.
8. Do not implement future milestones unless explicitly requested.
9. Update documentation if user-facing behavior changed.

---

# 39. Recommended First Copilot Prompt

Use this after creating the repository:

```text
Read PLAN.md carefully.

We are building the minimal educational version of Pinecraft.

Do not implement the entire plan at once.

Start with Milestone 1 only:

- create a minimal Python Arcade project
- create the Arcade window
- create settings.py for basic constants
- implement an update and draw loop
- add requirements.txt
- add a minimal README with installation and run instructions

Keep the architecture simple and suitable for programming students.

Do not add player movement, terrain, inventory, enemies, crafting, or other later features yet.

After making the changes, summarize the created files and tell me how to run the project.
```

---

# 40. Recommended Prompt for Each Later Milestone

Use:

```text
Read PLAN.md and inspect the current project.

Implement Milestone X only.

Before changing code, briefly explain your proposed approach.

Keep the solution simple and educational.

Do not implement later milestones.

Preserve all TODO_STUDENT sections.

After implementation:

1. run the game or perform the relevant sanity check,
2. report any problems,
3. summarize the changes,
4. suggest the next logical milestone without implementing it.
```

---

# 41. Feature Request Template

When adding a feature later:

```text
Read PLAN.md first.

I want to add this feature:

[FEATURE]

Constraints:

- keep it understandable for students
- make the smallest useful change
- avoid new dependencies
- do not refactor unrelated systems
- add simple debug/sanity checks where useful
- preserve TODO_STUDENT tasks

First inspect the current implementation and propose the change.
Then implement it.
```

---

# 42. Student Exercise Creation Template

When preparing a new classroom exercise:

```text
Read PLAN.md and inspect the existing project.

Create a student exercise for:

[TOPIC]

Difficulty:
[BEGINNER / INTERMEDIATE / ADVANCED]

The exercise should:

- have a clear German explanation
- contain a TODO_STUDENT marker
- provide hints
- not reveal the complete solution
- leave the rest of the game functional
- be verifiable by running and interacting with the game

Do not solve the exercise.
```

---

# 42A. Additional Advanced Student Projects

## ⭐⭐⭐ Torch Variations

Create different light sources:

- weak candle
- normal torch
- blue magic torch
- glowing crystal

Students modify light radius and strength without touching the shader architecture.

---

## ⭐⭐⭐ Night Creatures

Create an enemy that only appears when:

```python
is_night(time_of_day)
```

---

## ⭐⭐⭐ Glowing Blocks

Add blocks such as lava, magic crystals, glowing mushrooms, or radioactive ore that emit light.

---

## ⭐⭐⭐ Shader Experiment

For students specifically interested in graphics programming, provide an optional shader exercise.

Ideas:

- change torch-light falloff
- add subtle torch flicker
- add underwater color tint
- add a damage vignette
- add heat distortion near lava

This is an optional advanced path and must never block ordinary game development.

---

# 43. Scope Control

The following features are explicitly NOT part of the initial implementation:

- multiplayer
- physically accurate global illumination
- liquid simulation
- complex crafting UI
- armor
- experience points
- enchantments
- redstone-like systems
- advanced pathfinding
- mod/plugin API
- dynamic weather
- complex save format
- world editor
- mobile support

These may become later student or teacher projects.

---

# 44. Guiding Principle

Whenever choosing between:

> a more sophisticated architecture

and

> code that a 12-year-old can understand and modify

prefer the second option unless the simpler version causes a serious technical problem.

Pinecraft may use more sophisticated internals for chunk streaming and shaders where they substantially improve the game experience.

Those internals should be hidden behind simple APIs whenever possible.

The goal is still to make students say:

> "I changed the code, and now something new exists in the game."

That feedback loop is the core of the project.
