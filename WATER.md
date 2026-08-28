# WATER.md — Pinecraft Water System

## 1. Goal

Add a simple but convincing **2D water simulation** to Pinecraft.

Water should:

- have a volume per world cell
- fall downward
- spread horizontally
- form pools
- create waterfalls
- flow into caves and holes
- react when blocks are placed or removed
- work with Pinecraft's infinite chunk-based world
- perform well enough for classroom computers

The goal is **not realistic fluid dynamics**.

The goal is a predictable, visually convincing block-game water system that remains understandable and maintainable.

---

# 2. Core Concept

Water is **not a normal block type**.

A world cell contains two separate pieces of information:

```python
block = world.get_block(x, y)
water = world.get_water(x, y)
```

For example:

```text
AIR   + 0.0 water
AIR   + 0.5 water
AIR   + 1.0 water
STONE + 0.0 water
```

This separation is important.

Do NOT implement water simply as:

```python
world.set_block(x, y, WATER)
```

Water is a separate simulation layer.

This will make future features easier, such as:

- underwater plants
- ladders in water
- rain
- swimming
- lava
- flowing liquids
- waterlogged objects

---

# 3. Water Volume

Each world cell stores a floating-point water amount.

Use:

```python
0.0 <= water <= 1.0
```

Meaning:

```text
0.0 = no water
0.25 = quarter-full
0.5 = half-full
0.75 = three-quarter-full
1.0 = full water block
```

Define constants:

```python
MAX_WATER = 1.0
MIN_WATER = 0.001
MIN_FLOW = 0.01
```

Very small amounts below `MIN_WATER` should become zero.

Very small flows below `MIN_FLOW` should be ignored to prevent endless tiny floating-point changes.

---

# 4. Basic Simulation Rules

Water follows three priorities:

## Priority 1 — Down

Water should always try to fall downward first.

## Priority 2 — Sideways

Water remaining after downward flow should spread left and right.

## Priority 3 — Stop

If the water has reached equilibrium, it becomes inactive until something nearby changes.

Do not implement upward pressure initially.

---

# 5. Downward Flow

For a cell:

```text
(x, y)
```

first inspect:

```text
(x, y - 1)
```

If the cell below is not solid, water should fill it.

Example:

```text
Before

    1.0
    0.0
    0.0


After

    0.0
    0.0
    1.0
```

Water should therefore fall quickly rather than slowly leaking downward.

Conceptually:

```python
space_below = MAX_WATER - water_below
flow = min(water_here, space_below)
```

Then:

```python
water_here -= flow
water_below += flow
```

Downward movement has priority over horizontal spreading.

---

# 6. Horizontal Equalization

If water cannot move farther downward, it should spread horizontally.

For two neighboring cells:

```text
A       B
1.0     0.0
```

their ideal equilibrium is:

```text
0.5     0.5
```

Calculate:

```python
total = water_a + water_b
target = total / 2

flow = water_a - target
```

Only move water if:

```python
flow >= MIN_FLOW
```

Repeated updates naturally distribute water across larger spaces.

Example:

```text
Initial

1.0   0.0   0.0

Later

0.5   0.5   0.0

Eventually

0.33  0.33  0.33
```

The algorithm does not need to reach perfect mathematical equilibrium instantly.

Gradual movement looks more natural.

---

# 7. Left/Right Bias

The simulation must not accidentally prefer one direction.

Do not create behavior where:

```text
water always flows right first
```

simply because cells are processed from left to right.

Possible solutions:

- alternate horizontal processing direction each tick
- calculate both horizontal flows before applying them
- use a next-state/delta buffer

Prefer the delta-buffer approach described below.

---

# 8. Do Not Modify Water While Iterating

Do not directly modify the source water state while calculating the current simulation tick.

Otherwise the result depends on iteration order.

Instead use:

```python
current_water
water_changes
```

or equivalent chunk-local structures.

Conceptually:

```python
water_changes = {}

for cell in active_cells:
    calculate_flows(cell, water_changes)

apply_changes(water_changes)
```

For a flow from A to B:

```python
water_changes[A] -= flow
water_changes[B] += flow
```

After all active cells have been processed:

```python
apply_water_changes()
```

This preserves water volume and avoids directional artifacts.

---

# 9. Conservation of Water

Normal water simulation must conserve water.

If the simulation starts with:

```text
100.0 units
```

it should still contain approximately:

```text
100.0 units
```

after many updates.

Water may only be created or destroyed by explicit game mechanics such as:

```python
add_water(...)
remove_water(...)
```

Because floating-point arithmetic can introduce tiny errors, values may be clamped:

```python
water = max(0.0, min(MAX_WATER, water))
```

But do not use clamping to hide major conservation bugs.

---

# 10. Water System API

Create a dedicated system.

Suggested structure:

```python
class WaterSystem:
    def update(self, world, delta_time):
        ...

    def add_water(self, x, y, amount):
        ...

    def remove_water(self, x, y, amount):
        ...

    def get_water(self, x, y):
        ...

    def activate(self, x, y):
        ...
```

The rest of the game should not need to understand the details of water simulation.

---

# 11. Active Water Cells

Do NOT simulate every water cell in the entire explored world every frame.

Maintain:

```python
active_water_cells = set()
```

Only active cells participate in simulation.

When water changes at:

```text
(x, y)
```

activate:

```text
(x, y)
(x - 1, y)
(x + 1, y)
(x, y - 1)
(x, y + 1)
```

A helper may be used:

```python
activate_neighborhood(x, y)
```

---

# 12. Sleeping Water

Water that has reached equilibrium should stop being simulated.

For example:

```text
█████████████
█           █
█~~~~~~~~~~~█
█████████████
```

A stable pool should consume almost no CPU.

If a water cell produces no meaningful flow for several simulation ticks, remove it from the active set.

It becomes active again when something nearby changes.

Examples:

- player removes a block
- player places a block
- new water arrives
- neighboring water changes
- chunk becomes active
- future explosions modify terrain

---

# 13. Block Changes Must Wake Water

Whenever a block changes, nearby water must be activated.

For example:

```python
world.break_block(x, y)
```

should eventually cause:

```python
water_system.activate_neighborhood(x, y)
```

Example:

```text
Before:

~~~~~~~~~~~~
████ ███████
     ^
     hole created
```

Water should immediately begin flowing into the new hole.

The same applies when placing blocks into or next to water.

---

# 14. Simulation Tick Rate

Do not run the water simulation on every rendered frame.

Rendering may run at:

```text
60 FPS
```

while water can update at:

```text
10–20 updates per second
```

For example:

```python
WATER_TICK_RATE = 15
WATER_TICK_INTERVAL = 1 / WATER_TICK_RATE
```

Accumulate time:

```python
water_timer += delta_time

if water_timer >= WATER_TICK_INTERVAL:
    water_system.update(...)
    water_timer -= WATER_TICK_INTERVAL
```

This improves performance and makes water behavior easier to tune.

---

# 15. Maximum Work Per Tick

Because Pinecraft has an infinite world, a huge waterfall could potentially activate thousands of cells.

Protect the frame rate.

Use a maximum such as:

```python
MAX_WATER_UPDATES_PER_TICK = 2000
```

If more active cells exist, process the remaining cells during future ticks.

The exact number should be tuned through profiling.

Do not allow water simulation to freeze the game.

---

# 16. Chunk Integration

Pinecraft uses an effectively infinite chunk-based world.

Water must integrate with chunks.

Each chunk should store its own water data.

Conceptually:

```python
chunk.water
```

Do not create one global infinite water array.

Possible representation:

```python
chunk.water[(local_x, y)] = amount
```

A sparse dictionary is attractive because most cells contain no water.

Do not store entries for:

```python
water == 0.0
```

unless profiling shows a dense array is significantly better.

---

# 17. Water Across Chunk Boundaries

Water must flow seamlessly between chunks.

The `WaterSystem` should work with world coordinates:

```python
get_water(x, y)
set_water(x, y, amount)
```

The world/chunk system handles conversion internally.

Water simulation code should not contain special logic like:

```python
if local_x == CHUNK_WIDTH - 1:
    # special case
```

unless absolutely necessary.

The normal world-coordinate API should make chunk boundaries mostly invisible.

---

# 18. Unloaded Chunks

Do not simulate water in distant unloaded chunks.

When a chunk unloads:

- preserve its water state if necessary
- remove its cells from the active simulation set

When it loads again:

- restore water state
- activate relevant water cells near boundaries or unstable areas

It is acceptable for distant water to effectively pause while its chunk is unloaded.

Pinecraft does not need to simulate an infinite world while the player is somewhere else.

---

# 19. Water Generation

World generation may create water.

Examples:

- oceans
- lakes
- underground pools

Generated water should be deterministic from the world seed.

Large naturally generated bodies of water should preferably begin in a stable state rather than requiring thousands of simulation ticks to settle.

For example, an ocean can be generated directly as full cells:

```python
water = 1.0
```

below sea level.

Do not generate an ocean by creating one water source and waiting for it to fill millions of cells.

---

# 20. Sea Level

Introduce:

```python
SEA_LEVEL = ...
```

Terrain generation can use this to create oceans and lakes.

Conceptually:

```text
                 mountain
                   /\
                  /  \
~~~~~~~~~~~~~~~~~/    \~~~~~~~~~~  SEA_LEVEL
```

If terrain is below sea level and exposed appropriately, generation may fill it with water.

---

# 21. Rendering Water

Water volume determines visible water height.

Example:

```python
visible_height = water_amount * TILE_SIZE
```

Water should fill the cell from bottom to top.

Examples:

```text
1.00  ████████
0.75
      ████████
      ████████
      ████████

0.50
      ████████
      ████████

0.25
      ████████
```

The actual renderer may use sprites, geometry, or a dedicated water rendering pass depending on the existing Pinecraft architecture.

---

# 22. Visual Water Levels

Internally use floats.

For rendering, optionally quantize water into approximately 8 visual levels:

```python
visual_level = round(water_amount * 8)
```

This creates a pleasant block-game aesthetic:

```text
1/8
2/8
3/8
4/8
5/8
6/8
7/8
8/8
```

Do not quantize the actual simulation unless there is a good reason.

---

# 23. Water Surface

Only the top exposed part of water needs a visible surface.

Possible later visual improvements:

- slightly animated surface
- waves
- transparent water
- underwater tint
- reflection highlight
- bubbles
- waterfall particles

These are rendering features and should remain separate from the simulation.

---

# 24. Interaction With Solid Blocks

Normal solid blocks cannot contain water initially.

Examples:

```text
STONE -> water must be 0
DIRT  -> water must be 0
GRASS -> water must be 0
```

When placing a solid block into water, choose one simple behavior for the first implementation:

**Recommended:** displaced water is removed.

Do not attempt complicated displacement physics initially.

This can be improved later.

---

# 25. Player Interaction

Water should eventually affect the player.

Do not implement all player-water mechanics as part of the first water milestone.

Possible later features:

- swimming
- slower movement
- reduced gravity
- buoyancy
- drowning
- bubbles
- underwater darkness
- underwater shader
- splashing

Keep the initial water simulation independent from player physics.

---

# 26. Water and Lighting

Pinecraft already has lighting, darkness, torches, and shaders.

Water should eventually interact visually with that system.

Possible effects:

- darker underwater areas
- blue/green underwater tint
- reduced torch radius underwater
- light attenuation through water
- subtle distortion

These are later rendering improvements.

Do not complicate the first water implementation with shader changes.

First make the simulation correct and performant.

---

# 27. No Pressure Initially

Do NOT initially implement:

- water compression
- upward pressure
- pumps
- communicating-vessel physics
- realistic hydrostatic pressure

For version 1:

```text
DOWN
then
LEFT/RIGHT
```

is enough.

This already creates:

- waterfalls
- pools
- flooding
- draining
- partial water levels

---

# 28. Possible Future Pressure System

If needed later, cells may support slight compression:

```python
MAX_WATER = 1.0
MAX_COMPRESSION = 0.1
```

Internal amounts could temporarily reach:

```text
1.1
```

Excess pressure could push water upward.

This is explicitly a later feature.

Do not implement it unless requested.

---

# 29. Water Sources

Do not implement infinite Minecraft-style water sources initially.

All water should represent actual conserved volume.

For example:

```python
water_system.add_water(x, y, 1.0)
```

adds exactly one block-volume of water.

This makes the simulation easier to understand and creates interesting gameplay.

Infinite water sources may be added later as a deliberate game mechanic.

---

# 30. Debug Tools

Water needs good visualization for development.

Add an optional water debug mode.

Useful information:

```text
water amount
active/sleeping status
chunk boundary
number of active cells
water updates per second
time spent updating water
```

Possible overlay:

```text
0.00  0.00  0.00
0.25  0.50  0.25
1.00  1.00  1.00
████  ████  ████
```

A keyboard shortcut may toggle the debug overlay.

---

# 31. Important Performance Rule

Never do:

```python
for every chunk ever generated:
    for every cell:
        update_water()
```

Water simulation must scale primarily with:

```text
currently active water
```

not:

```text
size of explored world
```

This is essential for Pinecraft's infinite-world architecture.

---

# 32. Suggested Implementation Milestones

## Milestone 1 — Water Data Layer

Implement:

- water amount storage
- `get_water()`
- `set_water()`
- `add_water()`
- `remove_water()`
- chunk integration

Do not simulate anything yet.

Verify manually that water amounts can be added and inspected.

---

## Milestone 2 — Basic Rendering

Render water based on its volume.

Verify:

```text
0.25
0.50
0.75
1.00
```

produce visibly different heights.

---

## Milestone 3 — Falling Water

Implement only downward movement.

Test situations such as:

```text
W
.
.
█
```

Water should fall until blocked.

Do not implement sideways flow yet.

---

## Milestone 4 — Horizontal Flow

Implement left/right equalization.

Verify that:

```text
██████████
█   W    █
██████████
```

eventually forms a level pool.

---

## Milestone 5 — Delta Buffer

Ensure all flows are calculated before being applied.

Verify that water does not systematically prefer left or right.

---

## Milestone 6 — Active Cells

Implement:

```python
active_water_cells
```

Only active water should update.

Stable pools should eventually sleep.

---

## Milestone 7 — Terrain Interaction

Breaking blocks near water wakes the simulation.

Placing blocks near water also wakes neighboring cells.

Test creating a hole underneath a stable lake.

---

## Milestone 8 — Chunk Boundaries

Verify water can flow:

```text
chunk 4 -> chunk 5
```

without special visible behavior.

Test both positive and negative chunk coordinates.

---

## Milestone 9 — Chunk Loading

Ensure active water does not keep unloaded chunks alive unnecessarily.

Restore/re-activate appropriate water when chunks return.

---

## Milestone 10 — Natural Water

Integrate water with procedural generation.

Add:

- sea level
- oceans and/or lakes
- optional underground pools

Generated large bodies of water should begin mostly stable.

---

## Milestone 11 — Performance Cleanup

Add:

- maximum updates per tick
- active-cell count
- update-time debug information
- cleanup of tiny water amounts

Test large waterfalls and flooded caves.

---

## Milestone 12 — Visual Polish

Only after the simulation works well, consider:

- transparency
- animated surfaces
- waterfalls
- particles
- underwater tint
- shader effects

---

# 33. Manual Test Scenarios

Before considering the system stable, manually test these scenarios.

## Test A — Falling Column

```text
 W
 .
 .
 .
 █
```

Expected:

Water falls to the bottom.

---

## Test B — Flat Container

```text
██████████
█ W      █
██████████
```

Expected:

Water spreads and forms a level pool.

---

## Test C — Waterfall

```text
~~~~~~
████ █████
     .
     .
     .
██████████
```

Expected:

Water flows through the opening and falls downward.

---

## Test D — Two Pools Connected

```text
~~~~█
█████
    █~~~~
██████████
```

Remove the separating block.

Expected:

Water redistributes.

---

## Test E — Chunk Boundary

Place water directly next to a chunk boundary.

Expected:

It flows across normally.

---

## Test F — Stable Lake

Create a large stable lake.

Expected:

After settling, active-cell count becomes very small.

---

## Test G — Large Waterfall

Create a large source high above a cave.

Expected:

The game remains responsive while water spreads.

---

# 34. Copilot Rules

When implementing this plan:

1. Read `PLAN.md` first to understand the existing Pinecraft architecture.
2. Read `WATER.md` completely.
3. Inspect the current world/chunk implementation before modifying anything.
4. Do not redesign unrelated Pinecraft systems.
5. Implement one water milestone at a time.
6. Keep water separate from block IDs.
7. Preserve deterministic chunk generation.
8. Do not introduce a physics library.
9. Do not introduce a testing framework.
10. Do not implement realistic fluid dynamics.
11. Do not implement pressure unless explicitly requested.
12. Do not implement infinite water sources unless explicitly requested.
13. Do not modify shaders until the basic simulation works.
14. Prefer simple readable code over clever optimization.
15. Profile before introducing complicated performance techniques.

---

# 35. Recommended First Copilot Prompt

```text
Read PLAN.md and WATER.md completely.

Inspect the existing Pinecraft world and chunk architecture.

We are now implementing WATER.md Milestone 1 only:

Water Data Layer.

Requirements:

- water is separate from block IDs
- each cell may contain a water amount from 0.0 to 1.0
- water data belongs to the chunk/world system
- provide simple world-coordinate APIs for get_water(), set_water(), add_water(), and remove_water()
- zero-water cells should preferably not consume unnecessary storage
- positive and negative chunk coordinates must work
- do not implement water movement yet
- do not implement rendering yet
- do not implement player swimming
- do not modify shaders
- do not implement later WATER.md milestones

Before changing code:

1. inspect the relevant existing files,
2. explain how water data should fit the current architecture,
3. identify the files you intend to modify.

Then implement Milestone 1.

Afterwards summarize the changes and give me a simple way to manually verify that water amounts can be stored correctly.
```

---

# 36. Prompt for Later Water Milestones

```text
Read PLAN.md and WATER.md.

Inspect the current implementation.

Implement WATER.md Milestone [NUMBER] only.

Keep the implementation consistent with the existing Pinecraft architecture.

Important:

- do not implement future milestones
- do not redesign unrelated systems
- keep water separate from block IDs
- preserve infinite chunk streaming
- keep student-facing APIs simple
- do not introduce pytest or another testing framework

Before editing, briefly explain your approach.

After implementation:

1. run Pinecraft or perform an appropriate sanity check,
2. report any problems,
3. summarize exactly what changed,
4. explain how I can manually test this milestone,
5. suggest the next WATER.md milestone without implementing it.
```

---

# 37. Guiding Principle

The water system should create the illusion of a living fluid world without becoming a fluid-dynamics engine.

Prefer:

```text
simple rules
+
good visuals
+
good performance
```

over physical accuracy.

The desired result is that a player can dig a hole underneath a lake and immediately think:

> "Oh no."

...and then watch the cave flood.