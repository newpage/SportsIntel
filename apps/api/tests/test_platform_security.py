from dataclasses import replace
import json
import logging

from fastapi.testclient import TestClient
import pytest

from app.configuration import Settings
from app.main import app


ADMIN_KEY = "test-admin-key-with-at-least-32-characters"


def _client_settings(**changes):
    app.state.settings = replace(app.state.settings, **changes)


def test_admin_endpoints_require_api_key() -> None:
    _client_settings(admin_key=ADMIN_KEY)
    client = TestClient(app)

    missing = client.post("/api/sports/nfl/history/clear")
    invalid = client.post(
        "/api/sports/nfl/history/clear",
        headers={"X-Admin-Key": "incorrect"},
    )
    valid = client.post(
        "/api/sports/nfl/history/clear",
        headers={"X-Admin-Key": ADMIN_KEY},
    )
    deleted = client.delete(
        "/api/sports/nfl/missing/history",
        headers={"X-Admin-Key": ADMIN_KEY},
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert missing.json() == {"detail": "Unauthorized"}
    assert valid.status_code == 200
    assert deleted.status_code == 200


def test_admin_endpoint_is_unauthorized_when_key_is_not_configured() -> None:
    _client_settings(admin_key=None)

    response = TestClient(app).post(
        "/api/sports/nfl/history/clear",
        headers={"X-Admin-Key": ADMIN_KEY},
    )

    assert response.status_code == 401


def test_public_and_admin_rate_limits_are_independent() -> None:
    _client_settings(
        admin_key=ADMIN_KEY,
        public_rate_limit=2,
        admin_rate_limit=1,
    )
    client = TestClient(app)

    assert client.get("/api/sports").status_code == 200
    assert client.get("/api/sports").status_code == 200
    limited = client.get("/api/sports")
    assert limited.status_code == 429
    assert limited.headers["Retry-After"] == "60"

    headers = {"X-Admin-Key": ADMIN_KEY}
    assert client.post(
        "/api/sports/nfl/history/clear", headers=headers
    ).status_code == 200
    assert client.post(
        "/api/sports/nfl/history/clear", headers=headers
    ).status_code == 429


def test_health_endpoint_is_not_rate_limited() -> None:
    _client_settings(public_rate_limit=1)
    client = TestClient(app)

    for _ in range(5):
        assert client.get("/health").status_code == 200


def test_security_headers_and_production_hsts() -> None:
    client = TestClient(app)
    development = client.get("/health")

    assert development.headers["X-Content-Type-Options"] == "nosniff"
    assert development.headers["X-Frame-Options"] == "DENY"
    assert development.headers["Referrer-Policy"] == "no-referrer"
    assert development.headers["Content-Security-Policy"].startswith(
        "default-src 'none'"
    )
    assert "Strict-Transport-Security" not in development.headers
    assert development.headers["X-Request-ID"]

    _client_settings(environment="production")
    production = client.get("/health")
    assert production.status_code == 503
    assert production.headers["Strict-Transport-Security"] == (
        "max-age=31536000; includeSubDomains"
    )


def test_health_contract_is_complete_and_secret_safe() -> None:
    _client_settings(
        environment="test",
        version="14.8-test",
        build_timestamp="2026-08-05T12:00:00Z",
        git_commit="abc1234",
        database_url_configured=True,
    )

    response = TestClient(app).get("/health")
    payload = response.json()

    assert response.status_code == 200
    assert payload["application"]["name"] == "SportsIntel API"
    assert payload["postgresql"]["configured"] is True
    assert payload["snapshot_store"]["snapshot_store_type"] == "memory"
    assert payload["version"] == "14.8-test"
    assert payload["build_timestamp"] == "2026-08-05T12:00:00Z"
    assert payload["git_commit"] == "abc1234"
    assert payload["environment"] == "test"
    assert "password" not in response.text.lower()
    assert "database_url" not in response.text.lower()
    assert ADMIN_KEY not in response.text


def test_structured_request_log_excludes_sensitive_values(caplog) -> None:
    _client_settings(admin_key=ADMIN_KEY)

    with caplog.at_level(logging.INFO, logger="sportsintel.access"):
        response = TestClient(app).post(
            "/api/sports/nfl/history/clear",
            headers={
                "X-Admin-Key": ADMIN_KEY,
                "Authorization": "Bearer secret-token",
            },
        )

    record = json.loads(caplog.records[-1].message)
    assert response.status_code == 200
    assert set(record) == {
        "timestamp",
        "path",
        "status",
        "latency_ms",
        "client_ip",
        "request_id",
    }
    assert ADMIN_KEY not in caplog.text
    assert "secret-token" not in caplog.text


def test_production_configuration_requires_security_variables() -> None:
    with pytest.raises(ValueError, match="Missing required production variables"):
        Settings.from_environment({"SPORTSINTEL_ENV": "production"})


def test_valid_production_configuration() -> None:
    settings = Settings.from_environment(
        {
            "SPORTSINTEL_ENV": "production",
            "SPORTSINTEL_ADMIN_KEY": "a" * 40,
            "SPORTSINTEL_CORS_ORIGINS": "https://sports.example.com",
            "SPORTSINTEL_PUBLIC_RATE_LIMIT": "60",
            "SPORTSINTEL_ADMIN_RATE_LIMIT": "20",
            "SPORTSINTEL_TRUST_PROXY_HEADERS": "true",
            "SPORTSINTEL_BUILD_TIMESTAMP": "2026-08-05T12:00:00Z",
            "SPORTSINTEL_GIT_COMMIT": "abc1234",
            "SPORTSINTEL_VERSION": "0.2.0",
            "NFL_SNAPSHOT_STORE": "postgres",
            "DATABASE_URL": "postgresql://user:password@database/sportsintel",
        }
    )

    assert settings.production is True
    assert settings.cors_origins == ("https://sports.example.com",)
    assert settings.trust_proxy_headers is True


def test_trusted_proxy_uses_last_forwarded_address(caplog) -> None:
    _client_settings(trust_proxy_headers=True)

    with caplog.at_level(logging.INFO, logger="sportsintel.access"):
        response = TestClient(app).get(
            "/api/sports",
            headers={"X-Forwarded-For": "spoofed, 203.0.113.10"},
        )

    assert response.status_code == 200
    assert json.loads(caplog.records[-1].message)["client_ip"] == "203.0.113.10"


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("SPORTSINTEL_PUBLIC_RATE_LIMIT", "0", "between 1 and 100000"),
        ("SPORTSINTEL_ADMIN_RATE_LIMIT", "not-a-number", "must be an integer"),
        ("SPORTSINTEL_TRUST_PROXY_HEADERS", "sometimes", "true or false"),
        ("SPORTSINTEL_CORS_ORIGINS", "*", "cannot use"),
    ],
)
def test_configuration_rejects_invalid_values(name, value, message) -> None:
    with pytest.raises(ValueError, match=message):
        Settings.from_environment({name: value})
