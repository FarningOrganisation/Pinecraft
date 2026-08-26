from mobs.monster import Monster
from sprite_animation import SpriteAnimation

class Zombie(Monster):

    def __init__(self, world, x, y):
        animations = {
            "walking": SpriteAnimation(["assets/textures/mobs/zombi1.png"]),
        }
        super().__init__(world, x, y, animations, "walking")
