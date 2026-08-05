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
