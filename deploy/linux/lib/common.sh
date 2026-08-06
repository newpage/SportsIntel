#!/usr/bin/env bash

repo_root() { cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd; }
deployment_root() { printf '%s\n' "${SPORTSINTEL_DEPLOY_ROOT:-/opt/sportsintel}"; }
shared_root() { printf '%s/shared\n' "$(deployment_root)"; }
env_file() { printf '%s\n' "${SPORTSINTEL_ENV_FILE:-$(shared_root)/production.env}"; }
compose() { docker compose --project-name "${COMPOSE_PROJECT_NAME:-sportsintel}" --env-file "$(env_file)" -f "$(repo_root)/docker-compose.production.yml" "$@"; }
require_command() { command -v "$1" >/dev/null 2>&1 || { echo "Required command not found: $1" >&2; return 1; }; }
require_tools() { for tool in "$@"; do require_command "$tool"; done; }
require_env_file() {
  local file; file="$(env_file)"
  [[ -r "$file" ]] || { echo "Production environment file is not readable: $file" >&2; return 1; }
  local mode
  mode="$(stat -c '%a' "$file" 2>/dev/null || stat -f '%Lp' "$file")"
  [[ "$mode" == "600" || "$mode" == "640" ]] || { echo "Environment file permissions must be 600 or 640 (found $mode)" >&2; return 1; }
}
load_environment() {
  require_env_file
  set -a
  # shellcheck disable=SC1090
  source "$(env_file)"
  set +a
}
file_mode() { stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1"; }
file_owner() { stat -c '%U:%G' "$1" 2>/dev/null || stat -f '%Su:%Sg' "$1"; }
validate_database_url() {
  require_command python3
  python3 - "$DATABASE_URL" "$POSTGRES_USER" "$POSTGRES_PASSWORD" <<'PY'
import sys
from urllib.parse import unquote, urlparse

message = "DATABASE_URL is invalid. Use a URL-safe password or percent-encode it."
try:
    parsed = urlparse(sys.argv[1])
    port = parsed.port
except (TypeError, ValueError):
    raise SystemExit(message)
valid = (
    parsed.scheme == "postgresql"
    and parsed.hostname == "postgres"
    and port is not None
    and parsed.path not in {"", "/"}
    and parsed.username is not None
    and parsed.password is not None
    and unquote(parsed.username) == sys.argv[2]
    and unquote(parsed.password) == sys.argv[3]
)
if not valid:
    raise SystemExit(message)
PY
}
container_health() {
  local service="$1" id
  id="$(compose ps -q "$service" 2>/dev/null || true)"
  [[ -n "$id" ]] || { echo "absent"; return; }
  docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id" 2>/dev/null || echo "unknown"
}
wait_for_postgres() {
  local timeout="${SPORTSINTEL_POSTGRES_TIMEOUT_SECONDS:-120}" elapsed=0 health
  [[ "$timeout" =~ ^[0-9]+$ && "$timeout" -gt 0 ]] || { echo "SPORTSINTEL_POSTGRES_TIMEOUT_SECONDS must be a positive integer" >&2; return 1; }
  while ((elapsed < timeout)); do
    health="$(container_health postgres)"
    if [[ "$health" == "healthy" ]] && compose exec -T postgres pg_isready -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"; then
      echo "PostgreSQL is healthy and accepting connections."
      return 0
    fi
    ((elapsed % 10 == 0)) && echo "Waiting for PostgreSQL (${elapsed}s/${timeout}s; health=$health)"
    sleep 2; elapsed=$((elapsed + 2))
  done
  echo "PostgreSQL readiness timed out after ${timeout}s." >&2
  compose logs --tail=100 postgres >&2 || true
  return 1
}
wait_url() {
  local name="$1" url="$2" attempts="${3:-60}"
  for ((attempt=1; attempt<=attempts; attempt++)); do
    if curl --fail --silent --show-error --max-time 10 "$url" >/dev/null; then echo "$name is healthy"; return 0; fi
    sleep 2
  done
  echo "$name did not become healthy: $url" >&2; return 1
}
metadata_value() {
  local key="$1" file
  file="$(shared_root)/deployment.json"
  [[ -r "$file" ]] || return 1
  sed -n "s/.*\"${key}\": \"\([^\"]*\)\".*/\1/p" "$file" | head -n 1
}
