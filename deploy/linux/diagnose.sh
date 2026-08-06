#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=deploy/linux/lib/common.sh
source "$(dirname "$0")/lib/common.sh"
output=""
while (($#)); do case "$1" in --output) output="${2:-}"; [[ -n "$output" ]] || exit 2; shift 2 ;; *) echo "Usage: $0 [--output <file>]" >&2; exit 2 ;; esac; done
require_tools docker sed df id python3
collect() {
  echo "=== OS ==="; sed -n '1,20p' /etc/os-release 2>/dev/null || uname -a
  echo "=== Runtime ==="; docker --version 2>&1 || true; docker compose version 2>&1 || true
  echo "=== Identity ==="; id
  echo "=== Directories ==="
  for path in "$(deployment_root)" "$(shared_root)" "$(deployment_root)/backups" "$(deployment_root)/.docker" "$(repo_root)"; do [[ -e "$path" ]] && echo "$path owner=$(file_owner "$path") mode=$(file_mode "$path")"; done
  echo "=== Compose ==="; compose ps 2>&1 || true
  echo "postgres=$(container_health postgres) api=$(container_health api) web=$(container_health web)"
  echo "=== DATABASE_URL fields (no credentials) ==="
  if [[ -r "$(env_file)" ]]; then
    load_environment
    python3 - "$DATABASE_URL" <<'PY'
import sys
from urllib.parse import urlparse
try:
    value = urlparse(sys.argv[1])
    print(f"scheme={value.scheme} host={value.hostname} port={value.port} database={value.path.lstrip('/')} username_present={bool(value.username)} password_present={bool(value.password)}")
except Exception:
    print("DATABASE_URL parsing failed")
PY
  else echo "environment file unavailable"; fi
  echo "=== Disk ==="; df -h "$(deployment_root)" 2>&1 || true
  echo "=== Loopback ports ==="
  if command -v ss >/dev/null 2>&1; then ss -ltn || true; fi
  echo "=== Sanitized logs ==="
  compose logs --tail=100 postgres api web 2>&1 | sed -E 's#postgresql://[^[:space:]]+#postgresql://[REDACTED]#g; s/(X-Admin-Key|Authorization|password)=?[^[:space:]]*/\1=[REDACTED]/Ig' || true
}
if [[ -n "$output" ]]; then umask 077; collect >"$output"; chmod 600 "$output"; echo "Diagnostics written with mode 600: $output"; else collect; fi
