#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=deploy/linux/lib/common.sh
source "$(dirname "$0")/lib/common.sh"
require_tools curl docker
mode="${1:---external}"
api="http://127.0.0.1:${API_PORT:-8300}"; web="http://127.0.0.1:${WEB_PORT:-3300}"
if [[ "$mode" == "--external" ]]; then
  [[ -n "${SPORTSINTEL_PUBLIC_URL:-}" ]] || { echo "SPORTSINTEL_PUBLIC_URL is required for external smoke tests" >&2; exit 2; }
  code="$(curl --silent --output /dev/null --write-out '%{http_code}' "${SPORTSINTEL_PUBLIC_URL}/")"
  [[ "$code" == "401" ]] || { echo "Preview authentication is not enforced (expected 401, got $code)" >&2; exit 1; }
  [[ -n "${SPORTSINTEL_PREVIEW_USER:-}" && -n "${SPORTSINTEL_PREVIEW_PASSWORD:-}" ]] || { echo "Preview credentials are required for authenticated smoke tests" >&2; exit 2; }
  curl --fail --silent --show-error --user "${SPORTSINTEL_PREVIEW_USER}:${SPORTSINTEL_PREVIEW_PASSWORD}" "${SPORTSINTEL_PUBLIC_URL}/" >/dev/null
fi
wait_url API "$api/health"
wait_url Web "$web/"
health="$(curl --fail --silent --show-error "$api/health")"; [[ "$health" == *'"status":"healthy"'* ]] || { echo "Production health is not healthy" >&2; exit 1; }
store="$(curl --fail --silent --show-error "$api/api/sports/nfl/snapshot-store/health")"; [[ "$store" == *'"snapshot_persistence":true'* ]] || { echo "PostgreSQL snapshot persistence is unavailable" >&2; exit 1; }
command_center="$(curl --fail --silent --show-error "$api/api/sports/nfl/command-center")"; [[ "$command_center" == *'"affects_prediction":false'* ]] || { echo "Command Center response contract check failed" >&2; exit 1; }
curl --fail --silent --show-error "$api/api/mlb" >/dev/null
code="$(curl --silent --output /dev/null --write-out '%{http_code}' -X POST "$api/api/sports/nfl/history/clear")"; [[ "$code" == "401" ]] || { echo "Admin endpoint did not reject unauthenticated request" >&2; exit 1; }
if command -v ss >/dev/null 2>&1 && ss -ltn | grep -Eq '(^|[[:space:]])0\.0\.0\.0:5432|\[::\]:5432'; then echo "PostgreSQL is publicly listening" >&2; exit 1; fi
echo "SportsIntel smoke tests passed ($mode)."
