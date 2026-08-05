from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import os
from urllib.parse import urlparse


VALID_ENVIRONMENTS = {"development", "test", "production"}


def _positive_int(
    environment: Mapping[str, str],
    name: str,
    default: int,
) -> int:
    raw = environment.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 1 or value > 100_000:
        raise ValueError(f"{name} must be between 1 and 100000")
    return value


def _boolean(
    environment: Mapping[str, str],
    name: str,
    default: bool,
) -> bool:
    raw = environment.get(name, str(default)).strip().lower()
    if raw in {"true", "1", "yes", "on"}:
        return True
    if raw in {"false", "0", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def _origins(environment: Mapping[str, str]) -> tuple[str, ...]:
    raw = environment.get("SPORTSINTEL_CORS_ORIGINS", "")
    origins = tuple(value.strip().rstrip("/") for value in raw.split(",") if value.strip())
    for origin in origins:
        parsed = urlparse(origin)
        if origin == "*" or parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(
                "SPORTSINTEL_CORS_ORIGINS must contain comma-separated "
                "HTTP(S) origins and cannot use '*'"
            )
    return origins


@dataclass(frozen=True)
class Settings:
    environment: str
    admin_key: str | None
    cors_origins: tuple[str, ...]
    public_rate_limit: int
    admin_rate_limit: int
    trust_proxy_headers: bool
    database_url_configured: bool
    snapshot_store: str
    version: str
    build_timestamp: str
    git_commit: str

    @property
    def production(self) -> bool:
        return self.environment == "production"

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> Settings:
        values = os.environ if environment is None else environment
        deployment_environment = values.get(
            "SPORTSINTEL_ENV", "development"
        ).strip().lower()
        if deployment_environment not in VALID_ENVIRONMENTS:
            raise ValueError(
                "SPORTSINTEL_ENV must be development, test, or production"
            )

        admin_key = values.get("SPORTSINTEL_ADMIN_KEY", "").strip() or None
        cors_origins = _origins(values)
        snapshot_store = values.get("NFL_SNAPSHOT_STORE", "").strip().lower()
        database_url = values.get("DATABASE_URL", "").strip()
        build_timestamp = values.get(
            "SPORTSINTEL_BUILD_TIMESTAMP", "unknown"
        ).strip()
        git_commit = values.get("SPORTSINTEL_GIT_COMMIT", "unknown").strip()
        version = values.get("SPORTSINTEL_VERSION", "0.2.0").strip()

        if deployment_environment == "production":
            missing = [
                name
                for name, present in (
                    ("DATABASE_URL", bool(database_url)),
                    ("SPORTSINTEL_ADMIN_KEY", bool(admin_key)),
                    ("SPORTSINTEL_CORS_ORIGINS", bool(cors_origins)),
                    (
                        "SPORTSINTEL_BUILD_TIMESTAMP",
                        build_timestamp not in {"", "unknown"},
                    ),
                    (
                        "SPORTSINTEL_GIT_COMMIT",
                        git_commit not in {"", "unknown"},
                    ),
                )
                if not present
            ]
            if missing:
                raise ValueError(
                    "Missing required production variables: "
                    + ", ".join(missing)
                )
            if snapshot_store != "postgres":
                raise ValueError(
                    "NFL_SNAPSHOT_STORE must be postgres in production"
                )
            if admin_key is not None and (
                len(admin_key) < 32 or "replace" in admin_key.lower()
            ):
                raise ValueError(
                    "SPORTSINTEL_ADMIN_KEY must be at least 32 characters "
                    "and must not be a placeholder in production"
                )
            if any(not origin.startswith("https://") for origin in cors_origins):
                raise ValueError(
                    "SPORTSINTEL_CORS_ORIGINS must use HTTPS in production"
                )
            try:
                parsed_timestamp = datetime.fromisoformat(
                    build_timestamp.replace("Z", "+00:00")
                )
            except ValueError as exc:
                raise ValueError(
                    "SPORTSINTEL_BUILD_TIMESTAMP must be an ISO-8601 timestamp"
                ) from exc
            if parsed_timestamp.tzinfo is None:
                raise ValueError(
                    "SPORTSINTEL_BUILD_TIMESTAMP must include a timezone"
                )
            if len(git_commit) < 7 or "replace" in git_commit.lower():
                raise ValueError(
                    "SPORTSINTEL_GIT_COMMIT must contain a real commit identifier"
                )

        if not version:
            raise ValueError("SPORTSINTEL_VERSION cannot be empty")

        return cls(
            environment=deployment_environment,
            admin_key=admin_key,
            cors_origins=cors_origins,
            public_rate_limit=_positive_int(
                values, "SPORTSINTEL_PUBLIC_RATE_LIMIT", 60
            ),
            admin_rate_limit=_positive_int(
                values, "SPORTSINTEL_ADMIN_RATE_LIMIT", 20
            ),
            trust_proxy_headers=_boolean(
                values, "SPORTSINTEL_TRUST_PROXY_HEADERS", False
            ),
            database_url_configured=bool(database_url),
            snapshot_store=snapshot_store or (
                "postgres" if database_url else "memory"
            ),
            version=version,
            build_timestamp=build_timestamp or "unknown",
            git_commit=git_commit or "unknown",
        )
