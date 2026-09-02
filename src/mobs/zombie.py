from mobs.monster import Monster
from mobs.registry import register_mob
from paths import textures_dir
from sprite_animation import SpriteAnimation
from ids import STICK, STONE_SWORD

@register_mob("Zombie")
class Zombie(Monster):

    def __init__(self, world, x, y, drop_table: dict[int, float] | None = None):
        mob_texture_dir = textures_dir("mobs", "zombie")
        animations = {
            "walking": SpriteAnimation([mob_texture_dir / "zombi1.png"]),
        }
        loot_table = {STICK: 0.55, STONE_SWORD: 0.08} if drop_table is None else drop_table
        super().__init__(world, x, y, animations, "walking", drop_table=loot_table)
