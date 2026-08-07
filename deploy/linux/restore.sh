#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=deploy/linux/lib/common.sh
source "$(dirname "$0")/lib/common.sh"
require_tools docker
backup="${1:-}"; yes=false; [[ "${2:-}" == "--yes" || "${1:-}" == "--yes" ]] && yes=true
[[ -f "$backup" ]] || { echo "Usage: $0 <backup.dump> [--yes]" >&2; exit 2; }
load_environment
acquire_operation_lock
compose exec -T postgres pg_restore --list <"$backup" >/dev/null || { echo "Backup validation failed: $backup" >&2; exit 1; }
if ! $yes; then read -r -p "Restore into the configured production database? Type RESTORE: " confirmation; [[ "$confirmation" == "RESTORE" ]] || { echo "Restore cancelled."; exit 1; }; fi
"$(dirname "$0")/backup.sh"
compose stop api web
restore_failure() {
  local code=$?
  trap - ERR INT TERM
  echo "Restore failed after application services were stopped." >&2
  echo "API and web remain stopped to avoid serving against a partially restored database." >&2
  echo "Review PostgreSQL logs and the pre-restore backup, then complete recovery before restarting services." >&2
  exit "$code"
}
trap restore_failure ERR INT TERM
# Variables expand inside the PostgreSQL container.
# shellcheck disable=SC2016
compose exec -T postgres sh -c 'pg_restore --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --clean --if-exists --no-owner' <"$backup"
compose up -d
"$(dirname "$0")/smoke-test.sh" --internal
trap - ERR INT TERM
echo "Restore completed and validated."
