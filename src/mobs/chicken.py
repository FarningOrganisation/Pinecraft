from paths import textures_dir
from sprite_animation import SpriteAnimation
from world import World

from mobs.mob import Mob


class Chicken(Mob):
    def __init__(self, world: World, x, y):
        super().__init__(world, x, y, health=3, speed=120)
        text_dir = textures_dir("mobs")
        self.animations = {
            "walking": SpriteAnimation([text_dir / "chicken.png"]),
        }
        self.set_state("walking")
