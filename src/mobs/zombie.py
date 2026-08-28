from mobs.monster import Monster
from paths import textures_dir
from sprite_animation import SpriteAnimation

class Zombie(Monster):

    def __init__(self, world, x, y):
        mob_texture_dir = textures_dir("mobs")
        animations = {
            "walking": SpriteAnimation([mob_texture_dir / "zombi1.png"]),
        }
        super().__init__(world, x, y, animations, "walking")
