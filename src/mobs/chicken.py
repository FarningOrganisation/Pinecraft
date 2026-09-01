from paths import textures_dir
from sprite_animation import SpriteAnimation
from world import World

from mobs.mob import Mob


class Chicken(Mob):
    def __init__(self, world: World, x, y):
        text_dir = textures_dir("mobs", "chicken")
        animations = {
            "walking": SpriteAnimation([text_dir / "chicken.png"]),
        }
        default_state = "walking"
        super().__init__(world, x, y, health=3, speed=120, animations=animations, default_state=default_state)
