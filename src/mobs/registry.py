"""Zentrale Registry fuer speicherbare Mob-Typen."""

from __future__ import annotations

from collections.abc import Callable


MOB_REGISTRY: dict[str, type] = {}


def register_mob(type_name: str | None = None) -> Callable[[type], type]:
    """Registriert eine Mob-Klasse unter einem stabilen Save-Typnamen."""

    def decorator(mob_class: type) -> type:
        resolved_name = str(type_name or getattr(mob_class, "MOB_TYPE", mob_class.__name__)).strip()
        if not resolved_name:
            raise ValueError("Mob-Typname darf nicht leer sein")
        MOB_REGISTRY[resolved_name] = mob_class
        setattr(mob_class, "MOB_TYPE", resolved_name)
        return mob_class

    return decorator


def get_registered_mob_class(type_name: str):
    """Liefert die registrierte Mob-Klasse fuer den Save-Typnamen."""
    if not isinstance(type_name, str):
        return None
    return MOB_REGISTRY.get(type_name.strip())
