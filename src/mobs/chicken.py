from paths import textures_dir
from sprite_animation import SpriteAnimation
from world import World
from ids import EGG, FEATHER

from mobs.mob import Mob


class Chicken(Mob):
    def __init__(self, world: World, x, y, drop_table: dict[int, float] | None = None):
        text_dir = textures_dir("mobs", "chicken")
        animations = {
            "walking": SpriteAnimation([text_dir / "chicken.png"]),
        }
        default_state = "walking"
        loot_table = {FEATHER: 0.4, EGG: 0.2} if drop_table is None else drop_table
        super().__init__(
            world,
            x,
            y,
            health=3,
            speed=120,
            animations=animations,
            default_state=default_state,
            drop_table=loot_table,
        )
