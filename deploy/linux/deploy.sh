#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=deploy/linux/lib/common.sh
source "$(dirname "$0")/lib/common.sh"
ref="${1:-}"
[[ -n "$ref" ]] || { echo "Usage: $0 <reviewed-commit-or-tag>" >&2; exit 2; }
root="$(repo_root)"; cd "$root"
"$root/deploy/linux/preflight.sh" "$ref"
load_environment

phase="initialize"; prior_commit="$(git rev-parse HEAD)"; original_env="$(env_file)"
had_application=false; [[ -n "$(compose ps -q api web 2>/dev/null)" ]] && had_application=true
candidate="$(shared_root)/release.env.candidate"; metadata="$(shared_root)/deployment.json"
last_result="$(shared_root)/last-deployment"
failure_handler() {
  local code=$?
  trap - ERR INT TERM
  echo "Deployment failed during phase: $phase" >&2
  printf 'result=failed\nphase=%s\ntime=%s\n' "$phase" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$last_result" || true
  chmod 660 "$last_result" 2>/dev/null || true
  rm -f "$candidate"
  git checkout --detach "$prior_commit" >/dev/null 2>&1 || true
  export SPORTSINTEL_ENV_FILE="$original_env"
  if $had_application; then
    echo "Attempting to restore the prior application containers; PostgreSQL data is preserved." >&2
    if compose build api web >/dev/null 2>&1; then
      compose up -d api web >/dev/null 2>&1 || true
    fi
  else
    compose stop api web >/dev/null 2>&1 || true
  fi
  echo "PostgreSQL was not deleted. Inspect with: COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-sportsintel} $root/deploy/linux/status.sh" >&2
  echo "First-install cleanup: $root/deploy/linux/reset-preview.sh" >&2
  exit "$code"
}
trap failure_handler ERR INT TERM
fail_for_rehearsal() {
  if [[ -n "${SPORTSINTEL_TEST_FAIL_PHASE:-}" && "$SPORTSINTEL_TEST_FAIL_PHASE" == "$phase" ]]; then
    echo "Triggering CI-only deployment failure rehearsal at phase: $phase" >&2
    return 1
  fi
}

phase="resolve-release"
commit="$(git rev-parse --verify "${ref}^{commit}")"
previous="$(metadata_value deployed_git_commit 2>/dev/null || printf '%s' "$prior_commit")"
git checkout --detach "$commit"
timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; version="${SPORTSINTEL_VERSION_OVERRIDE:-0.2.0}"
phase="prepare-environment"; umask 027
grep -Ev '^(SPORTSINTEL_(ENV|VERSION|BUILD_TIMESTAMP|GIT_COMMIT))=' "$original_env" >"$candidate"
printf 'SPORTSINTEL_ENV=production\nSPORTSINTEL_VERSION=%s\nSPORTSINTEL_BUILD_TIMESTAMP=%s\nSPORTSINTEL_GIT_COMMIT=%s\n' "$version" "$timestamp" "$commit" >>"$candidate"
chmod 640 "$candidate"; export SPORTSINTEL_ENV_FILE="$candidate"; load_environment
phase="build-images"; compose build --pull api web
phase="start-postgresql"; compose up -d postgres
phase="wait-postgresql"; wait_for_postgres; fail_for_rehearsal
phase="apply-schema"
# Variables expand inside the PostgreSQL container.
# shellcheck disable=SC2016
compose exec -T postgres sh -c 'psql --set=ON_ERROR_STOP=1 --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --file=/docker-entrypoint-initdb.d/001_nfl_prediction_snapshots.sql'
echo "PostgreSQL schema applied successfully."
phase="start-application"; compose up -d api web
phase="smoke-test"; "$root/deploy/linux/smoke-test.sh" --internal
phase="promote-release"; mv "$candidate" "$(shared_root)/release.env"
SPORTSINTEL_ENV_FILE="$(shared_root)/release.env"; export SPORTSINTEL_ENV_FILE
printf '{\n  "deployed_git_commit": "%s",\n  "previous_release_commit": "%s",\n  "application_version": "%s",\n  "build_timestamp": "%s",\n  "deployment_timestamp": "%s"\n}\n' "$commit" "$previous" "$version" "$timestamp" "$timestamp" >"${metadata}.tmp"
mv "${metadata}.tmp" "$metadata"; chmod 660 "$metadata"
printf 'result=success\nphase=complete\ntime=%s\n' "$timestamp" >"$last_result"; chmod 660 "$last_result"
trap - ERR INT TERM
echo "Deployment succeeded at commit $commit"
