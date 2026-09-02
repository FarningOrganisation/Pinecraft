"""Boss-Grundklasse mit separater AI-State-Machine und Phasenlogik."""

from __future__ import annotations

from mobs.monster import Monster


class BossMonster(Monster):
    """Basisklasse fuer Boss-Mobs mit klar getrennter Gameplay- und Animationslogik.

    Gameplay-State-Machine:
    - ai_state steuert Verhalten (idle/chase/windup/attack/recover/stunned)
    - phase_state steuert Boss-Phasen (phase_1/phase_2/enraged)

    Animation:
    - current_animation_state / set_animation_state steuern nur Visuals.

        Persistenz:
        - Konkrete Boss-Subklassen koennen should_save() ueberschreiben,
            z. B. fuer Ritual-Bosse, die nach Reload neu beschworen werden muessen.
    """

    AI_IDLE = "idle"
    AI_CHASE = "chase"
    AI_WINDUP = "windup"
    AI_ATTACK = "attack"
    AI_RECOVER = "recover"
    AI_STUNNED = "stunned"

    PHASE_1 = "phase_1"
    PHASE_2 = "phase_2"
    PHASE_ENRAGED = "enraged"

    def __init__(
        self,
        world,
        x: float,
        y: float,
        animations,
        default_state,
        health: int = 40,
        activate_range: float = 520.0,
        aggro_duration: float = 3.5,
        attack_range: float | None = None,
        speed: float = 95.0,
        damage: int = 3,
        drop_table: dict[int, float] | None = None,
    ):
        super().__init__(
            world,
            x=x,
            y=y,
            animations=animations,
            default_state=default_state,
            health=health,
            activate_range=activate_range,
            aggro_duration=aggro_duration,
            attack_range=attack_range,
            speed=speed,
            damage=damage,
            drop_table=drop_table,
        )
        self.ai_state = self.AI_IDLE
        self.phase_state = self.PHASE_1
        self.state_timer = 0.0
        self.state_elapsed = 0.0
        self.enraged_health_ratio = 0.25
        self.phase2_health_ratio = 0.6

    def should_save(self) -> bool:
        """Default: Bosse werden momentan nicht gespeichert, da man einen Boss-Kampf nicht unterbrechen soll."""
        return False

    def _enter_ai_state(self, next_state: str, duration: float = 0.0) -> None:
        """Fuehrt einen Gameplay-State-Wechsel durch."""
        previous_state = self.ai_state
        if previous_state != next_state:
            self.on_ai_state_exit(previous_state, next_state)
        self.ai_state = next_state
        self.state_timer = max(0.0, float(duration))
        self.state_elapsed = 0.0
        if previous_state != next_state:
            self.on_ai_state_enter(previous_state, next_state)

    def on_ai_state_enter(self, previous_state: str, next_state: str) -> None:
        """Hook: Subklassen koennen beim Betreten eines AI-States reagieren."""
        return None

    def on_ai_state_exit(self, previous_state: str, next_state: str) -> None:
        """Hook: Subklassen koennen beim Verlassen eines AI-States reagieren."""
        return None

    def _update_phase_state(self) -> None:
        """Aktualisiert Boss-Phase auf Basis der verbleibenden HP."""
        if self.max_health <= 0:
            self.phase_state = self.PHASE_1
            return

        health_ratio = max(0.0, min(1.0, self.health / self.max_health))
        if health_ratio <= self.enraged_health_ratio:
            self.phase_state = self.PHASE_ENRAGED
        elif health_ratio <= self.phase2_health_ratio:
            self.phase_state = self.PHASE_2
        else:
            self.phase_state = self.PHASE_1

    def _choose_idle_or_chase(self, player) -> None:
        """Waehlt den naechsten Grundzustand ausserhalb von Attack-Sequenzen."""
        if player is None or not self._can_see_player(player):
            self._enter_ai_state(self.AI_IDLE, duration=0.2)
            return

        if self._is_player_in_attack_range(player):
            self._enter_ai_state(self.AI_WINDUP, duration=0.35)
            return

        self._enter_ai_state(self.AI_CHASE, duration=0.1)

    def _update_ai_state_machine(self, player, delta_time: float) -> None:
        """Steuert die Transitionen der Gameplay-State-Machine."""
        if self.ai_state == self.AI_WINDUP and self.state_timer <= 0.0:
            self._enter_ai_state(self.AI_ATTACK, duration=0.18)
            return

        if self.ai_state == self.AI_ATTACK and self.state_timer <= 0.0:
            self._enter_ai_state(self.AI_RECOVER, duration=0.4)
            return

        if self.ai_state == self.AI_RECOVER and self.state_timer <= 0.0:
            self._choose_idle_or_chase(player)
            return

        if self.ai_state in (self.AI_IDLE, self.AI_CHASE) and self.state_timer <= 0.0:
            self._choose_idle_or_chase(player)
            return

        if self.ai_state == self.AI_STUNNED and self.stun_timer <= 0.0:
            self._choose_idle_or_chase(player)
            return

        self.state_elapsed += max(0.0, float(delta_time))

    def _apply_ai_state_behavior(self, player, delta_time: float) -> None:
        """Fuehrt zustandsabhaengiges Verhalten aus; Subklassen koennen Hooks ueberschreiben."""
        handlers = {
            self.AI_IDLE: self.on_state_idle,
            self.AI_CHASE: self.on_state_chase,
            self.AI_WINDUP: self.on_state_windup,
            self.AI_ATTACK: self.on_state_attack,
            self.AI_RECOVER: self.on_state_recover,
            self.AI_STUNNED: self.on_state_stunned,
        }
        handler = handlers.get(self.ai_state, self.on_state_unknown)
        handler(player, delta_time)

    def on_state_idle(self, player, delta_time: float) -> None:
        """Default-Verhalten fuer AI_IDLE."""
        self.change_x = 0.0

    def on_state_chase(self, player, delta_time: float) -> None:
        """Default-Verhalten fuer AI_CHASE."""
        if player is None:
            self.change_x = 0.0
            return

        direction = self.player_direction(player)
        self.facing_right = direction >= 0
        speed_factor = 1.0
        if self.phase_state == self.PHASE_2:
            speed_factor = 1.12
        elif self.phase_state == self.PHASE_ENRAGED:
            speed_factor = 1.25
        self.change_x = direction * self.speed * speed_factor

    def on_state_windup(self, player, delta_time: float) -> None:
        """Default-Verhalten fuer AI_WINDUP."""
        self.change_x = 0.0

    def on_state_attack(self, player, delta_time: float) -> None:
        """Default-Verhalten fuer AI_ATTACK."""
        self.change_x *= 0.92
        if player is not None:
            self._update_attack_behavior(player, delta_time)

    def on_state_recover(self, player, delta_time: float) -> None:
        """Default-Verhalten fuer AI_RECOVER."""
        self.change_x *= 0.7

    def on_state_stunned(self, player, delta_time: float) -> None:
        """Default-Verhalten fuer AI_STUNNED."""
        self.change_x *= 0.85

    def on_state_unknown(self, player, delta_time: float) -> None:
        """Fallback fuer unbekannte AI-States."""
        self.change_x = 0.0

    def _sync_animation_with_ai_state(self) -> None:
        """Mappt Gameplay-States auf Animations-States."""
        mapping = {
            self.AI_IDLE: ("idle", "walking"),
            self.AI_CHASE: ("walking", "move", "idle"),
            self.AI_WINDUP: ("windup", "attack", "idle"),
            self.AI_ATTACK: ("attack", "walking", "idle"),
            self.AI_RECOVER: ("recover", "idle", "walking"),
            self.AI_STUNNED: ("stunned", "idle"),
        }

        for candidate in mapping.get(self.ai_state, ("idle", "walking")):
            if candidate in self.animations:
                self.set_animation_state(candidate)
                return

    def update_ai(self, delta_time: float, player):
        """Boss-AI mit separater Gameplay-State-Machine und Phasenlogik."""
        if not self.alive:
            self.vanish_after_death_timer = max(0.0, self.vanish_after_death_timer - delta_time)
            return

        if self.stun_timer > 0.0:
            self.stun_timer = max(0.0, self.stun_timer - delta_time)
            self._enter_ai_state(self.AI_STUNNED, duration=0.0)

        self._refresh_ground_state_for_ai()
        self._update_phase_state()

        self.state_timer = max(0.0, self.state_timer - delta_time)
        self._update_ai_state_machine(player, delta_time)
        self._apply_ai_state_behavior(player, delta_time)
        self._sync_animation_with_ai_state()

    def save_state(self) -> dict:
        """Persistiert Boss-spezifische State-Machine-Felder."""
        return {
            "ai_state": str(self.ai_state),
            "phase_state": str(self.phase_state),
            "state_timer": float(self.state_timer),
            "state_elapsed": float(self.state_elapsed),
        }

    def load_state(self, state: dict) -> None:
        """Stellt Boss-spezifische State-Machine-Felder wieder her."""
        ai_state = state.get("ai_state", self.ai_state)
        if isinstance(ai_state, str):
            self.ai_state = ai_state

        phase_state = state.get("phase_state", self.phase_state)
        if isinstance(phase_state, str):
            self.phase_state = phase_state

        try:
            self.state_timer = max(0.0, float(state.get("state_timer", self.state_timer)))
        except (TypeError, ValueError):
            self.state_timer = 0.0

        try:
            self.state_elapsed = max(0.0, float(state.get("state_elapsed", self.state_elapsed)))
        except (TypeError, ValueError):
            self.state_elapsed = 0.0
