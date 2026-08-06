#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=deploy/linux/lib/common.sh
source "$(dirname "$0")/lib/common.sh"
require_tools docker curl df sed git
file="$(env_file)"
echo "Docker access: $(docker info >/dev/null 2>&1 && echo available || echo unavailable)"
echo "Environment file: $file (owner=$(file_owner "$file" 2>/dev/null || echo unknown), mode=$(file_mode "$file" 2>/dev/null || echo unknown))"
if ! load_environment; then echo "Next command: verify $file ownership, mode 640, and required values."; exit 1; fi
echo "Deployed commit: $(metadata_value deployed_git_commit 2>/dev/null || echo unknown)"
echo "Current repository commit: $(git -C "$(repo_root)" rev-parse HEAD 2>/dev/null || echo unknown)"
echo "PostgreSQL container health: $(container_health postgres)"
echo "API container health: $(container_health api)"
echo "Web container health: $(container_health web)"
compose ps
if health="$(curl --fail --silent --show-error "http://127.0.0.1:${API_PORT:-8300}/health" 2>/dev/null)"; then
  echo "Database connectivity and schema reachability: $health"
else
  echo "Database connectivity and schema reachability: unavailable"
fi
echo "Loopback listeners:"
if command -v ss >/dev/null 2>&1; then ss -ltn | grep -E "127\\.0\\.0\\.1:(${API_PORT:-8300}|${WEB_PORT:-3300})([[:space:]]|$)" || echo "expected listeners not found"; else echo "ss unavailable"; fi
echo "Last deployment result:"
if [[ -r "$(shared_root)/last-deployment" ]]; then sed -n '1,10p' "$(shared_root)/last-deployment"; else echo "not recorded"; fi
df -h "$(deployment_root)"
echo "Container restart counts:"
while IFS= read -r container_id; do [[ -n "$container_id" ]] && docker inspect --format '{{.Name}} restarts={{.RestartCount}} started={{.State.StartedAt}}' "$container_id"; done < <(compose ps -q)
if [[ "$(container_health postgres)" != healthy || "$(container_health api)" != healthy || "$(container_health web)" != healthy ]]; then
  echo "Next command: $(repo_root)/deploy/linux/diagnose.sh --output /tmp/sportsintel-diagnostics.txt"
fi
