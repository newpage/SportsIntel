#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=deploy/linux/lib/common.sh
source "$(dirname "$0")/lib/common.sh"
require_tools git docker curl date sed
require_env_file
ref="${1:-}"
[[ -n "$ref" ]] || { echo "Usage: $0 <reviewed-commit-or-tag>" >&2; exit 2; }
root="$(repo_root)"; cd "$root"
[[ -z "$(git status --porcelain)" ]] || { echo "Deployment checkout is dirty; aborting." >&2; exit 1; }
git fetch --tags origin
commit="$(git rev-parse --verify "${ref}^{commit}" 2>/dev/null)" || { echo "Invalid Git ref: $ref" >&2; exit 1; }
previous="$(metadata_value deployed_git_commit 2>/dev/null || git rev-parse HEAD)"
git checkout --detach "$commit"
timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
version="${SPORTSINTEL_VERSION_OVERRIDE:-0.2.0}"
generated="$(shared_root)/release.env"
umask 027
grep -Ev '^(SPORTSINTEL_(ENV|VERSION|BUILD_TIMESTAMP|GIT_COMMIT))=' "$(env_file)" >"${generated}.tmp"
printf 'SPORTSINTEL_ENV=production\nSPORTSINTEL_VERSION=%s\nSPORTSINTEL_BUILD_TIMESTAMP=%s\nSPORTSINTEL_GIT_COMMIT=%s\n' "$version" "$timestamp" "$commit" >>"${generated}.tmp"
mv "${generated}.tmp" "$generated"; chmod 640 "$generated"
export SPORTSINTEL_ENV_FILE="$generated"
compose config --quiet
compose build --pull api web
compose up -d postgres
# Variables expand inside the PostgreSQL container.
# shellcheck disable=SC2016
compose exec -T postgres sh -c 'psql --set=ON_ERROR_STOP=1 --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --file=/docker-entrypoint-initdb.d/001_nfl_prediction_snapshots.sql'
compose up -d
"$root/deploy/linux/smoke-test.sh" --internal
metadata="$(shared_root)/deployment.json"
printf '{\n  "deployed_git_commit": "%s",\n  "previous_release_commit": "%s",\n  "application_version": "%s",\n  "build_timestamp": "%s",\n  "deployment_timestamp": "%s"\n}\n' "$commit" "$previous" "$version" "$timestamp" "$timestamp" >"${metadata}.tmp"
mv "${metadata}.tmp" "$metadata"; chmod 640 "$metadata"
echo "Deployment succeeded at commit $commit"
