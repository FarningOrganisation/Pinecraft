# LAVA.md — Pinecraft Lava System

## 1. Goal

Add lava to Pinecraft as a second simulated liquid.

Lava should:

- reuse the existing proven water simulation architecture
- use the same generic liquid-flow algorithm as water
- have its own independent volume layer and active state
- flow more slowly than water
- spread less aggressively than water
- emit light
- damage the player
- interact with water
- create obsidian when lava and water meet
- remain performant

The goal is **not realistic magma physics**.

The goal is a simple, readable, game-like lava system that feels clearly different from water without duplicating the working water simulation.

---

# 2. Core Architecture — Shared LiquidSystem

**Important architectural requirement:** Do not create a separate copy of the water simulation algorithm for lava.

The existing water simulation is already stable, optimized, and working well. Lava should reuse the same proven flow algorithm with different configuration parameters.

Refactor the existing `WaterSystem` into a generic `LiquidSystem` with the **smallest possible behavioral change**.

Conceptually:

```python id="1e5g9d"
water_system = LiquidSystem(
    liquid_type=WATER,
    config=WATER_CONFIG,
)

lava_system = LiquidSystem(
    liquid_type=LAVA,
    config=LAVA_CONFIG,
)
```

The generic `LiquidSystem` should contain shared simulation behavior:

```text id="2yizva"
LiquidSystem
├── downward flow
├── horizontal equalization
├── conservation logic
├── active-cell management
├── sleeping / stabilization
├── minimum-flow handling
├── work budget
└── simulation update
```

Water and lava provide different configuration values.

For example:

```python id="j5cy5p"
WATER_CONFIG = LiquidConfig(
    tick_rate=15,
    horizontal_flow_factor=0.25,
    min_flow=0.01,
    max_updates_per_tick=500,
    render_threshold=0.02,
)

LAVA_CONFIG = LiquidConfig(
    tick_rate=5,
    horizontal_flow_factor=0.10,
    min_flow=0.01,
    max_updates_per_tick=300,
    render_threshold=0.02,
)
```

These are example starting values only.

**When refactoring, preserve the currently working water values exactly.**

Do not change water behavior merely to make the abstraction cleaner.

---

# 3. Separate Runtime State

Although water and lava share the same simulation implementation, they must have independent runtime state.

Conceptually:

```text id="wqvb0r"
water
├── own liquid storage
├── own active cells
├── own simulation timer
└── own delta/change buffers

lava
├── own liquid storage
├── own active cells
├── own simulation timer
└── own delta/change buffers
```

Water and lava must therefore be able to update independently and at different rates.

Do not accidentally share:

- active sets
- queues
- timers
- delta buffers
- volume storage
- sleeping state

between water and lava.

---

# 4. Separate Liquid Storage

Water and lava should have separate volume layers.

A world cell may conceptually contain:

```python id="ipdsgd"
block = world.get_block(x, y)
water = world.get_water(x, y)
lava = world.get_lava(x, y)
```

Possible states:

```text id="k9pndp"
AIR   + water 0.0 + lava 0.0
AIR   + water 0.7 + lava 0.0
AIR   + water 0.0 + lava 1.0
STONE + water 0.0 + lava 0.0
```

Do not represent lava only as a normal block ID.

Do not combine water and lava into a single:

```text id="7d37pv"
liquid_type + amount
```

representation unless the existing architecture provides a strong reason to do so.

Keeping separate layers makes water/lava reactions easier to detect and reason about.

---

# 5. What Belongs in LiquidSystem?

Only behavior that genuinely applies to both liquids should be generalized.

Examples:

- downward flow
- horizontal equalization
- conservation
- active-cell management
- sleeping
- flow thresholds
- work limits
- update scheduling logic where appropriate

The generic system should know how to move a liquid.

It should not need to know the gameplay meaning of that liquid.

---

# 6. What Does NOT Belong in LiquidSystem?

Liquid-specific gameplay should remain outside the generic flow algorithm.

For example:

```text id="o9k7vf"
Lava
├── damages player
├── emits light
└── reacts with water

Water
├── swimming
├── drowning
└── future water-specific mechanics
```

Water/lava reactions should therefore be handled separately:

```text id="tixn91"
Water LiquidSystem ─┐
                    ├── LiquidInteractionSystem
Lava LiquidSystem ──┘
```

The interaction system can implement:

```text id="e1sj09"
WATER + LAVA -> OBSIDIAN
```

without adding obsidian-specific logic to the generic liquid-flow algorithm.

---

# 7. Critical Refactoring Rule

**Do not rewrite the working water algorithm while generalizing it.**

The process should be:

```text id="pbak8q"
working WaterSystem
        ↓
identify hardcoded water-specific parameters
        ↓
extract them into WATER_CONFIG
        ↓
generalize only what is necessary
        ↓
verify water behaves identically
        ↓
instantiate the same system for lava
```

Water behavior before and after the refactor should be effectively identical.

Do not combine this refactor with:

- new water physics
- rendering changes
- optimizations unrelated to lava
- lighting changes
- chunk-system changes

If some existing water behavior cannot cleanly be generalized, preserve it first and report the issue rather than redesigning everything.

---

# 8. Lava Volume

Use the same volume concept as water:

```python id="i3tdtr"
0.0 <= lava <= 1.0
```

Meaning:

```text id="t5sq20"
0.0 = no lava
0.5 = half-full
1.0 = full
```

Possible lava configuration:

```python id="t91b3z"
MAX_LAVA = 1.0
MIN_LAVA = 0.001
MIN_LAVA_FLOW = 0.01
```

Prefer expressing these through `LAVA_CONFIG` rather than introducing unnecessary lava-specific code.

---

# 9. Lava Must Feel Different From Water

Lava should use the same simulation algorithm but different parameters.

Water should feel:

```text id="yqfl43"
fast
fluid
responsive
```

Lava should feel:

```text id="vrn0k5"
slow
heavy
viscous
dangerous
```

The main differences should initially come from configuration rather than different algorithms.

---

# 10. Lava Tick Rate

Lava should update substantially more slowly than water.

For example:

```python id="kv3md1"
WATER_TICK_RATE = 15
LAVA_TICK_RATE = 5
```

These values are starting points.

Water and lava must have independent timers.

Conceptually:

```python id="8r2jva"
water_system.update_if_ready(delta_time)
lava_system.update_if_ready(delta_time)
```

Do not make lava update every rendered frame.

---

# 11. Downward Flow

Lava uses the same downward-flow algorithm as water.

It should strongly prefer falling downward.

Example:

```text id="yb02am"
L
.
.
█
```

eventually becomes:

```text id="2ww84n"
.
.
L
█
```

The slower simulation tick should make the movement feel heavier.

Do not create a separate lava-specific downward-flow algorithm unless genuinely necessary.

---

# 12. Horizontal Flow

Lava should spread less aggressively than water.

Use configuration to control this.

For example:

```python id="eib8tc"
LAVA_HORIZONTAL_FLOW_FACTOR = 0.10
```

versus a larger value for water.

The existing generic horizontal equalization algorithm should remain unchanged.

Stable lava basins must still eventually settle.

---

# 13. Active Lava Cells

The lava `LiquidSystem` instance must maintain its own active cells.

Conceptually:

```python id="5nrv74"
water_system.active_cells
lava_system.active_cells
```

Lava cells should sleep when stable.

Wake lava when:

- lava amount changes
- neighboring lava changes
- nearby terrain changes
- nearby water causes a reaction
- relevant world data loads

Stable lava should consume almost no simulation time.

---

# 14. Maximum Lava Work

Use the same work-budget mechanism already proven for water.

For example:

```python id="8fmegg"
MAX_LAVA_UPDATES_PER_TICK = 300
```

This may be lower than water because lava updates more slowly.

Do not allow a huge lava flow to freeze the game.

The goal is:

> stable FPS is more important than lava reaching equilibrium quickly.

---

# 15. Lava Rendering

Use the same general volume-rendering concept as water.

Internally:

```python id="1cgg4x"
lava_amount = 0.37
```

Visually:

```text id="xj36ik"
3/8 block
```

Use approximately eight visual height levels.

For example:

```python id="8hrj2u"
visual_level = ceil(lava_amount * 8)
```

Do not quantize the simulation value.

---

# 16. Lava Render Threshold

Like water, tiny residual amounts should not create visible thin strips.

Define an appropriate render threshold:

```python id="qqg0jj"
LAVA_RENDER_THRESHOLD = 0.02
```

Conceptually:

```python id="v7c0p6"
if lava_amount < LAVA_RENDER_THRESHOLD:
    render nothing
else:
    render quantized lava height
```

This threshold affects rendering only.

It must not modify conservation or flow calculations.

---

# 17. Water/Lava Interaction Architecture

Water and lava simulations should remain independent.

Create a dedicated interaction layer.

For example:

```python id="r0b2nd"
class LiquidInteractionSystem:
    def check_cell(self, world, x, y):
        ...
```

or another architecture that fits the existing project.

Responsibilities:

```text id="68w4nf"
LiquidSystem
    -> moves liquids

LiquidInteractionSystem
    -> handles reactions between liquid types
```

Do not make `LiquidSystem` contain hardcoded logic such as:

```python id="crn5j7"
if self.type == LAVA and water_nearby:
    create_obsidian()
```

unless there is a compelling reason.

---

# 18. First Water + Lava Rule

For the first implementation, use one simple rule:

> Meaningful water touching meaningful lava turns the contacted lava into obsidian.

Do not initially reproduce every Minecraft water/lava rule.

Start with:

```text id="o89w14"
WATER + LAVA -> OBSIDIAN
```

This is simple, intuitive, and easy for students to understand.

---

# 19. Reaction Threshold

Do not react to microscopic floating-point residue.

Define:

```python id="j97x10"
LIQUID_REACTION_THRESHOLD = 0.05
```

Only react when the relevant liquid amount exceeds this threshold.

This prevents something like:

```text id="37q46x"
water = 0.0002
lava  = 0.7
```

from unexpectedly creating obsidian.

---

# 20. Same-Cell Reaction

If both liquid layers contain meaningful amounts in the same cell:

```python id="jqgm55"
water = world.get_water(x, y)
lava = world.get_lava(x, y)
```

then trigger the reaction.

Conceptually:

```text id="ac6k68"
WATER
+
LAVA
  ↓
OBSIDIAN
```

Afterward, no lava should remain inside the obsidian cell.

---

# 21. Neighbor Reaction

Liquids may also meet across cell boundaries.

Check only immediate relevant neighbors:

```text id="qf63ss"
above
below
left
right
```

For example:

```text id="z14i7i"
W L
```

should be able to produce:

```text id="2nqqzy"
W O
```

where:

```text id="sm1h5i"
O = obsidian
```

Avoid scanning the entire liquid world for contacts.

---

# 22. Recommended Obsidian Rule

For the first implementation:

> Water touching lava converts the lava cell into obsidian.

So:

```text id="44mmko"
Before:

W L

After:

W O
```

Water remains.

Lava is consumed.

This creates useful behavior where flowing water can progressively solidify a lava pool.

Example:

```text id="0k3pdb"
W -> L L L L
```

may eventually become:

```text id="dfmgox"
W    O O O O
```

depending on flow and contact.

---

# 23. Reaction Ownership

Avoid both liquid systems independently creating obsidian.

There should be one authoritative reaction path.

For example:

```python id="qiyts5"
liquid_interactions.react_water_lava(...)
```

This function should be responsible for:

- determining whether reaction occurs
- consuming lava
- placing obsidian
- waking nearby liquids
- notifying rendering/lighting if necessary

This prevents duplicate reactions.

---

# 24. Wake Liquids After Reaction

Obsidian changes terrain.

Therefore after a reaction, nearby liquid cells must wake.

Conceptually:

```python id="nwn0mh"
water_system.activate_neighborhood(x, y)
lava_system.activate_neighborhood(x, y)
```

The exact API should follow the existing generic `LiquidSystem`.

---

# 25. Reaction Performance

Never do:

```text id="10hhxq"
for every water cell:
    for every lava cell:
        check collision
```

Only check reactions around:

- changed water cells
- changed lava cells
- terrain changes affecting liquids

Reaction work should scale with active liquids, not world size.

---

# 26. Lava and Player Collision

Lava itself should not be a solid block.

The player may enter lava cells.

Normal collision remains based on solid terrain blocks.

Lava-specific effects are handled separately.

---

# 27. Player Damage

Add lava damage only after flow and obsidian interaction work correctly.

Possible starting configuration:

```python id="6c92jo"
LAVA_DAMAGE_INTERVAL = 0.5
LAVA_DAMAGE = 2
```

If the player overlaps meaningful lava:

```python id="s6k3lo"
if lava_amount >= PLAYER_LAVA_THRESHOLD:
    player.take_damage(LAVA_DAMAGE)
```

Use a cooldown.

Do not apply damage every rendered frame.

---

# 28. Lava as a Light Source

Lava should emit light.

Use the existing **GPU/world-lighting shader architecture**.

Do not reintroduce CPU per-tile lighting.

Lava light should be able to illuminate otherwise dark caves.

---

# 29. Lava Light Appearance

Lava light should feel different from torch light.

Suggested characteristics:

- warm orange/red
- soft falloff
- medium radius
- strong near the lava surface
- optional subtle flicker later

Possible starting values:

```python id="8n4qfe"
LAVA_LIGHT_RADIUS = 140
LAVA_LIGHT_STRENGTH = 0.8
```

Tune visually.

---

# 30. Generic Local Light Sources

If it fits the current shader architecture cleanly, consider representing torch and lava lights through the same GPU light structure.

Conceptually:

```python id="b0m7hr"
LightSource(
    position,
    radius,
    strength,
    color,
)
```

Then:

```text id="p1vbgu"
World Lighting Shader
├── day/night ambient
├── cave/depth darkness
└── local lights
    ├── torches
    ├── lava
    └── future glowing blocks
```

Do not overengineer this if the existing torch system already has a simpler clean solution.

---

# 31. Do Not Treat Every Lava Cell As a Full Point Light

A lava lake may contain hundreds of cells.

Do not send every lava cell to the shader as an individual light.

For example:

```text id="iwnrrr"
LLLLLLLLLLLLLLLL
LLLLLLLLLLLLLLLL
```

must not create 32 full point lights unnecessarily.

This would scale poorly.

---

# 32. Simple Lava Light Selection

For the first implementation, only selected visible lava cells should produce shader lights.

Possible criteria:

- meaningful lava volume
- exposed to air
- near the visible surface of a lava pool
- near the camera/player

Example:

```python id="aljzax"
if lava_amount >= 0.5 and is_exposed_lava(x, y):
    consider_lava_light(...)
```

Then cap the result:

```python id="4t6m4y"
MAX_LAVA_LIGHTS = 16
```

If more candidates exist, prefer those nearest the player/camera.

---

# 33. Future Lava Light Merging

Later, nearby lava lights may be merged.

For example:

```text id="ozw0k9"
L L L L L
```

could produce:

```text id="g4jrmq"
  LIGHT
```

instead of five independent point lights.

Do not implement sophisticated clustering until profiling shows it is necessary.

---

# 34. Lava Animation

Do not make animation part of the initial simulation.

Later visual options include:

- animated surface
- moving texture
- brightness pulsing
- bubbles
- particles
- heat distortion
- glow flicker

Keep rendering and simulation separate.

---

# 35. Natural Lava Generation

Do not add natural lava immediately.

First make manually placed lava work correctly.

Later procedural generation may create:

- deep lava pools
- underground lava lakes
- lava falls

A possible rule:

```text id="q9ph93"
lava only generates below LAVA_DEPTH
```

Generation must remain deterministic.

---

# 36. Debug Information

Extend the existing liquid debug tools.

Useful information:

```text id="k5j2hx"
active water cells
active lava cells
processed water cells
processed lava cells
water update time
lava update time
water/lava reactions
visible lava lights
```

For an individual cell:

```text id="ljv4g2"
block: AIR
water: 0.00
lava: 0.73
```

---

# 37. Implementation Milestones

## Milestone 0 — Generalize WaterSystem

Before implementing lava:

1. inspect the current working `WaterSystem`
2. identify hardcoded water-specific values
3. create `LiquidConfig` or equivalent
4. extract the current water values into `WATER_CONFIG`
5. generalize `WaterSystem` into `LiquidSystem`
6. preserve independent runtime state
7. instantiate water through the generic system
8. verify water behavior is unchanged

Test:

- falling water
- horizontal spreading
- 6×1 and larger basin stabilization
- active-cell sleeping
- terrain changes waking water
- conservation
- current performance

**Do not continue with lava until water is confirmed working after the refactor.**

---

## Milestone 1 — Lava Data and Configuration

Create:

```text id="r03a5o"
LAVA_CONFIG
lava storage
lava LiquidSystem instance
lava active state
lava timer
```

Verify lava amounts can exist independently from water.

Do not implement lava movement differences beyond configuration yet.

---

## Milestone 2 — Lava Rendering

Render lava using:

- lava texture/color
- 1/8 visual height levels
- render threshold

Do not implement lighting yet.

---

## Milestone 3 — Lava Flow

Enable the generic `LiquidSystem` simulation for lava.

Configure it to:

- update more slowly
- spread horizontally more slowly
- preserve conservation
- stabilize correctly

Verify that no lava-specific duplicate flow algorithm has been introduced.

---

## Milestone 4 — Lava Active-State Performance

Verify:

- stable lava sleeps
- active lava respects the work budget
- large flows do not destroy FPS
- water and lava active state remain independent

---

## Milestone 5 — Terrain Interaction

Breaking or placing blocks near lava should wake nearby lava using the generic liquid-system APIs.

---

## Milestone 6 — Water/Lava Contact Detection

Create the dedicated interaction logic.

Detect meaningful water/lava contact.

For this milestone, debug output may simply report:

```text id="ewyl0u"
WATER/LAVA CONTACT
```

Do not create obsidian yet if separating detection makes debugging easier.

---

## Milestone 7 — Obsidian

Implement:

```text id="4wsw0h"
water touches lava
        ↓
lava becomes obsidian
```

Requirements:

- lava consumed
- water remains
- obsidian placed
- nearby liquids wake
- no duplicate reactions
- tiny residual liquid does not trigger reactions

---

## Milestone 8 — Player Damage

Make meaningful lava contact damage the player.

Use a damage cooldown.

---

## Milestone 9 — Lava Light

Integrate lava into the GPU world-lighting system.

Requirements:

- warm local light
- smooth falloff
- cave darkness can be overcome by nearby lava
- no CPU tile-light overlay
- bounded number of lava light sources
- torches continue working

---

## Milestone 10 — Lighting Performance

Test:

- one lava cell
- small pool
- large pool
- lava waterfall

Verify the number of shader lights remains bounded and FPS remains acceptable.

---

## Milestone 11 — Natural Generation

Optionally add deterministic underground lava generation.

---

## Milestone 12 — Visual Polish

Only after everything else works:

- animated lava
- bubbles
- particles
- glow pulse
- heat distortion
- water/lava reaction particles
- optional hiss sound

---

# 38. Manual Test Scenarios

## Test A — Water Regression Test

After `WaterSystem -> LiquidSystem` refactor:

```text id="6buvwy"
W
.
.
█
```

Expected:

Water behaves exactly as before.

Also test a basin.

Water must still stabilize and conserve volume.

---

## Test B — Independent Liquids

Place water and lava far apart.

Expected:

- water updates at water speed
- lava updates at lava speed
- neither active system affects the other's state

---

## Test C — Lava Falling

```text id="ovz09k"
L
.
.
█
```

Expected:

Lava falls downward, noticeably more slowly than water.

---

## Test D — Lava Basin

```text id="ufgn3p"
█████████
█   L   █
█████████
```

Expected:

Lava slowly spreads and eventually stabilizes.

---

## Test E — Water Touches Lava

```text id="2cpe0r"
W L
```

Expected:

```text id="bs0h5h"
W O
```

where:

```text id="fj4fg5"
O = obsidian
```

---

## Test F — Water Above Lava

```text id="iwwquh"
W
L
```

Expected:

Lava becomes obsidian.

---

## Test G — Flowing Water Into Lava

```text id="yprb11"
W -> L L L L
```

Expected:

Water can progressively solidify contacted lava.

---

## Test H — Lava Light

Place lava in a dark cave.

Expected:

- surrounding blocks are illuminated
- light is warm
- light falls off smoothly
- deep cave darkness remains outside the lava's radius

---

## Test I — Large Lava Pool

Create a large lava pool.

Expected:

- simulation remains responsive
- stable lava eventually sleeps
- shader does not receive one expensive light for every lava cell
- FPS remains acceptable

---

# 39. Copilot Rules

When implementing this plan:

1. Read `PLAN.md`.
2. Read `WATER.md`.
3. Read `LAVA.md`.
4. Inspect the current working water implementation before modifying it.
5. Do not duplicate the water flow algorithm to implement lava.
6. Water and lava must use the same generic `LiquidSystem`.
7. Preserve the currently working water behavior during generalization.
8. Water and lava must have independent storage.
9. Water and lava must have independent active state.
10. Water and lava must have independent update timing.
11. Do not mix lava-specific gameplay into generic liquid simulation.
12. Keep water/lava reaction logic centralized.
13. Refactor first, verify water, then implement lava.
14. Do not implement pressure.
15. Do not implement infinite lava sources.
16. Do not add complicated Minecraft-specific reaction rules initially.
17. Do not add natural lava generation before manually placed lava works.
18. Use the existing GPU lighting architecture for lava illumination.
19. Do not reintroduce CPU per-tile lighting.
20. Implement one milestone at a time.
21. Do not combine milestones unless explicitly requested.
22. Profile before introducing complicated optimizations.
23. If generalizing something would substantially rewrite the working water system, stop and explain why first.

---

# 40. Recommended First Copilot Prompt

```text id="zwd9a7"
Read PLAN.md, WATER.md, and LAVA.md completely.

Inspect the current working WaterSystem.

We are implementing LAVA.md Milestone 0 only:

Generalize WaterSystem into LiquidSystem.

The current water simulation is stable and working well.

The most important requirement is:

DO NOT CHANGE ITS BEHAVIOR.

Goal:

Extract the existing proven water-flow implementation into a generic LiquidSystem that can later be instantiated for both water and lava.

Please first inspect:

- WaterSystem
- water configuration/constants
- active-cell handling
- simulation timer
- volume storage/access
- delta/change buffers
- rendering interfaces

Identify which parts are genuinely water-specific and which parts are generic liquid simulation.

Then propose the smallest safe refactor.

Requirements:

- preserve the exact current water configuration values
- preserve current water flow behavior
- preserve conservation behavior
- preserve stabilization/sleeping
- preserve active-cell performance
- preserve rendering behavior
- do not implement lava yet
- do not implement obsidian
- do not modify lighting
- do not modify unrelated systems

Prefer extracting configuration over rewriting algorithms.

After implementation, manually verify:

1. falling water
2. horizontal spreading
3. basin stabilization
4. conservation
5. active-cell sleeping
6. terrain changes waking water
7. FPS while water is flowing

Report whether any water behavior changed.

Do not proceed to Milestone 1 automatically.
```

---

# 41. Recommended Lava Creation Prompt

After Milestone 0 is verified:

```text id="b7zzw2"
Read PLAN.md, WATER.md, and LAVA.md.

Milestone 0 is complete and water is working correctly through the new generic LiquidSystem.

Implement LAVA.md Milestone 1 only.

Create:

- LAVA_CONFIG
- separate lava volume storage
- independent lava active state
- independent lava simulation timer
- a lava LiquidSystem instance

Reuse the generic LiquidSystem.

Do not duplicate any water flow code.

Use starting lava configuration values that will later allow lava to be slower and more viscous than water.

Do not yet implement:

- water/lava reactions
- obsidian
- player damage
- lava lighting
- natural lava generation

After implementation, verify that water and lava state can exist independently.

Do not proceed to the next milestone automatically.
```

---

# 42. Recommended Water/Lava Interaction Prompt

When both liquids work:

```text id="r3l9n2"
Read PLAN.md, WATER.md, and LAVA.md.

Water and lava are now both working through the generic LiquidSystem.

Implement the water/lava interaction milestone.

Rule:

Meaningful water touching meaningful lava converts the lava cell into OBSIDIAN.

Use approximately:

LIQUID_REACTION_THRESHOLD = 0.05

Requirements:

- reaction logic must not be hardcoded into the generic LiquidSystem
- use the dedicated liquid-interaction layer
- only inspect changed cells and immediate neighbors
- never globally scan all water and lava cells
- lava is consumed
- contacted lava cell becomes obsidian
- water remains
- clear lava from the obsidian cell
- wake neighboring water and lava
- prevent duplicate reactions
- tiny residual amounts must not trigger reactions

Do not implement Minecraft's more complicated cobblestone/stone rules yet.

Before editing, explain where reaction checks fit into the current update pipeline.

After implementation, manually test:
- water beside lava
- water above lava
- flowing water entering a lava pool

Do not implement later milestones.
```

---

# 43. Recommended Lava Lighting Prompt

```text id="66xnhz"
Read PLAN.md, WATER.md, LAVA.md, and inspect the current world-lighting shader.

Lava flow and water/lava interaction are working.

Implement the lava-light milestone only.

Lava should act as a GPU-based local light source.

Requirements:

- integrate with the existing world-lighting shader
- do not create CPU per-tile lighting
- lava must illuminate deep caves
- use warm orange/red light
- use smooth radial falloff
- keep existing torch lights working

Do not send every lava cell as a point light.

For the first implementation:

- consider only visible lava
- ignore tiny lava volumes
- prefer exposed lava surface/edge cells
- cap the number of lava lights, for example MAX_LAVA_LIGHTS = 16
- if necessary, prioritize candidates nearest the camera/player

Possible starting values:

LAVA_LIGHT_RADIUS = 140
LAVA_LIGHT_STRENGTH = 0.8
MAX_LAVA_LIGHTS = 16

If it cleanly fits the current shader architecture, generalize torches and lava into a common local-light representation:

LightSource:
- position
- radius
- strength
- color

Do this only if it simplifies the current implementation.

Do not implement:
- shadows
- ray tracing
- global illumination
- complex lava-light clustering

After implementation report:

- how lava-light candidates are selected
- maximum shader light count
- whether torches and lava share the same shader path
- FPS with a larger lava pool
```

---

# 44. Guiding Principle

Lava should **reuse the engineering work already invested in water**, not duplicate it.

The architecture should become:

```text id="07tyah"
                 LiquidSystem
                /            \
          WATER_CONFIG     LAVA_CONFIG
               │               │
             Water            Lava
               \               /
                \             /
             LiquidInteractionSystem
                       │
                 water + lava
                       ↓
                    obsidian
```

Then other systems add the gameplay differences:

```text id="ozp00e"
Water
└── future swimming/drowning

Lava
├── damage
└── glowing local light
```

The desired player experience is:

```text id="ytxkmb"
dig into cave
      ↓
discover lava
      ↓
lava illuminates the darkness
      ↓
lava slowly flows toward player
      ↓
danger!
      ↓
redirect water toward lava
      ↓
water contacts lava
      ↓
obsidian forms
      ↓
lava glow disappears
```

The system should feel sophisticated to the player while remaining based on a small number of understandable, reusable systems.