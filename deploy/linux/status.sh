#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=deploy/linux/lib/common.sh
source "$(dirname "$0")/lib/common.sh"
require_tools docker curl df sed
require_env_file
echo "Deployed commit: $(metadata_value deployed_git_commit 2>/dev/null || echo unknown)"
echo "Previous commit: $(metadata_value previous_release_commit 2>/dev/null || echo unknown)"
echo "Application version: $(metadata_value application_version 2>/dev/null || echo unknown)"
compose ps
health="$(curl --fail --silent --show-error "http://127.0.0.1:${API_PORT:-8300}/health")"
printf 'Health: %s\n' "$health"
store="$(curl --fail --silent --show-error "http://127.0.0.1:${API_PORT:-8300}/api/sports/nfl/snapshot-store/health")"
printf 'Snapshot store: %s\n' "$store"
df -h "$(deployment_root)"
echo "Container restart counts:"
while IFS= read -r container_id; do
  [[ -n "$container_id" ]] || continue
  docker inspect --format '{{.Name}} restarts={{.RestartCount}} started={{.State.StartedAt}}' "$container_id"
done < <(compose ps -q)
