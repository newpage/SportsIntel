from __future__ import annotations

from threading import RLock

from app.sports.provider import SportProvider


class SportRegistry:
    """Thread-safe registry of installed sport providers."""

    def __init__(self) -> None:
        self._providers: dict[str, SportProvider] = {}
        self._lock = RLock()

    @staticmethod
    def _normalize(sport_key: str) -> str:
        normalized = sport_key.strip().lower()
        if not normalized:
            raise ValueError("sport_key cannot be empty")
        return normalized

    def register(self, provider: SportProvider, *, replace: bool = False) -> None:
        sport_key = self._normalize(provider.sport_key)
        with self._lock:
            if sport_key in self._providers and not replace:
                raise ValueError(f"Sport provider already registered: {sport_key}")
            self._providers[sport_key] = provider

    def unregister(self, sport_key: str) -> SportProvider | None:
        normalized = self._normalize(sport_key)
        with self._lock:
            return self._providers.pop(normalized, None)

    def get(self, sport_key: str) -> SportProvider:
        normalized = self._normalize(sport_key)
        with self._lock:
            provider = self._providers.get(normalized)
        if provider is None:
            raise KeyError(f"Unknown sport provider: {normalized}")
        return provider

    def contains(self, sport_key: str) -> bool:
        normalized = self._normalize(sport_key)
        with self._lock:
            return normalized in self._providers

    def keys(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._providers))

    def providers(self) -> tuple[SportProvider, ...]:
        with self._lock:
            return tuple(self._providers[key] for key in sorted(self._providers))

    def describe(self) -> list[dict]:
        return [provider.health() for provider in self.providers()]


sports_registry = SportRegistry()
