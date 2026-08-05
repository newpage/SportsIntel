#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=deploy/linux/lib/common.sh
source "$(dirname "$0")/lib/common.sh"
require_tools git docker curl
require_env_file
previous="$(metadata_value previous_release_commit 2>/dev/null || true)"
[[ "$previous" =~ ^[0-9a-fA-F]{7,40}$ ]] || { echo "No valid previous release commit in deployment metadata." >&2; exit 1; }
echo "Rolling application containers back to $previous; PostgreSQL data will be preserved."
"$(dirname "$0")/deploy.sh" "$previous"
echo "Rollback succeeded. Database-destructive migrations require a separate rollback plan."
