#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=deploy/linux/lib/common.sh
source "$(dirname "$0")/lib/common.sh"
ref="${1:-}"
[[ -n "$ref" ]] || { echo "Usage: $0 <reviewed-commit-or-tag>" >&2; exit 2; }
require_tools git docker curl python3 df grep
current_user="$(id -un)"
if [[ "$current_user" != "sportsintel" && "${SPORTSINTEL_ALLOW_NON_SERVICE_USER:-false}" != "true" ]]; then
  echo "Deployment must run as sportsintel. Use: sudo -iu sportsintel -- $0 $ref" >&2; exit 1
fi
root="$(repo_root)"; cd "$root"
[[ -z "$(git status --porcelain)" ]] || { echo "Deployment checkout is dirty; aborting." >&2; exit 1; }
git rev-parse --verify "${ref}^{commit}" >/dev/null 2>&1 || { echo "Invalid Git ref: $ref. Fetch it as sportsintel before deploying." >&2; exit 1; }
load_environment
shared="$(shared_root)"; service_home="$(deployment_root)"
docker_home="$service_home/.docker"; config_home="$service_home/.config"
[[ -d "$shared" && -w "$shared" ]] || { echo "Shared directory is not writable by sportsintel: $shared" >&2; exit 1; }
[[ -d "$docker_home" && -w "$docker_home" ]] || { echo "Docker configuration directory is missing or not writable: $docker_home" >&2; exit 1; }
[[ -d "$config_home" && -w "$config_home" ]] || { echo "Service configuration directory is missing or not writable: $config_home" >&2; exit 1; }
export HOME="$service_home" DOCKER_CONFIG="$docker_home" XDG_CONFIG_HOME="$config_home"
id -nG | tr ' ' '\n' | grep -qx docker || { echo "The sportsintel account must belong to the docker group; start a new login session after install.sh." >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker socket access failed for $current_user. Verify docker-group membership and reconnect." >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 is unavailable." >&2; exit 1; }
required=(SPORTSINTEL_PUBLIC_URL SPORTSINTEL_ADMIN_KEY SPORTSINTEL_CORS_ORIGINS NFL_SNAPSHOT_STORE DATABASE_URL POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD)
for name in "${required[@]}"; do
  [[ -n "${!name:-}" ]] || { echo "Missing required production variable: $name" >&2; exit 1; }
  [[ "${!name}" != *replace-with* ]] || { echo "Production variable is still a placeholder: $name" >&2; exit 1; }
  [[ "${!name}" != *sports.example.com* ]] || { echo "Production variable is still a placeholder: $name" >&2; exit 1; }
done
[[ "$NFL_SNAPSHOT_STORE" == "postgres" ]] || { echo "NFL_SNAPSHOT_STORE must be postgres" >&2; exit 1; }
[[ "${SPORTSINTEL_ENV:-}" == "production" ]] || { echo "SPORTSINTEL_ENV must be production" >&2; exit 1; }
[[ "$SPORTSINTEL_PUBLIC_URL" == https://* ]] || { echo "SPORTSINTEL_PUBLIC_URL must use HTTPS" >&2; exit 1; }
[[ ${#SPORTSINTEL_ADMIN_KEY} -ge 32 ]] || { echo "SPORTSINTEL_ADMIN_KEY must contain at least 32 characters" >&2; exit 1; }
[[ "${NEXT_PUBLIC_API_URL:-}" == "/api" ]] || { echo "NEXT_PUBLIC_API_URL must be /api" >&2; exit 1; }
[[ "${SPORTSINTEL_INTERNAL_API_URL:-}" == "http://api:8000" ]] || { echo "SPORTSINTEL_INTERNAL_API_URL must be http://api:8000" >&2; exit 1; }
validate_database_url
for port in "${WEB_PORT:-3300}" "${API_PORT:-8300}"; do
  if [[ -z "$(compose ps -q 2>/dev/null)" ]] && command -v ss >/dev/null 2>&1 && ss -ltn | grep -Eq "127\\.0\\.0\\.1:${port}([[:space:]]|$)"; then
    echo "Required loopback port is already in use: $port" >&2; exit 1
  fi
done
minimum_kb="${SPORTSINTEL_MIN_FREE_DISK_KB:-5242880}"
available_kb="$(df -Pk "$(deployment_root)" | awk 'NR==2 {print $4}')"
[[ "$available_kb" =~ ^[0-9]+$ && "$available_kb" -ge "$minimum_kb" ]] || { echo "Insufficient free disk: require at least ${minimum_kb}KB" >&2; exit 1; }
compose config --quiet
echo "Preflight passed for $(git rev-parse --verify "${ref}^{commit}")."
