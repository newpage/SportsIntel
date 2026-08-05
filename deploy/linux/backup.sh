#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=deploy/linux/lib/common.sh
source "$(dirname "$0")/lib/common.sh"
require_tools docker date find
require_env_file
backup_dir="${SPORTSINTEL_BACKUP_DIR:-$(deployment_root)/backups}"
retention_days="${SPORTSINTEL_BACKUP_RETENTION_DAYS:-14}"
[[ "$retention_days" =~ ^[0-9]+$ ]] || { echo "SPORTSINTEL_BACKUP_RETENTION_DAYS must be a nonnegative integer" >&2; exit 2; }
install -d -m 0700 "$backup_dir"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"; target="$backup_dir/sportsintel-$timestamp.dump"; temp="$target.partial"
umask 077; trap 'rm -f "$temp"' EXIT
# Variables expand inside the PostgreSQL container.
# shellcheck disable=SC2016
compose exec -T postgres sh -c 'pg_dump --username="$POSTGRES_USER" --format=custom "$POSTGRES_DB"' >"$temp"
[[ -s "$temp" ]] || { echo "Backup output is empty" >&2; exit 1; }
mv "$temp" "$target"; chmod 600 "$target"; trap - EXIT
find "$backup_dir" -type f -name 'sportsintel-*.dump' -mtime "+$retention_days" -delete
echo "Backup completed: $target"
