#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
scripts=("$root"/deploy/linux/*.sh "$root"/deploy/linux/lib/*.sh "$root"/deploy/apache/create-preview-user.sh)
for script in "${scripts[@]}"; do bash -n "$script"; done

# Match literal Compose interpolation syntax.
# shellcheck disable=SC2016
grep -q '127.0.0.1:${API_PORT:-8300}:8000' "$root/docker-compose.production.yml"
# Match literal Compose interpolation syntax.
# shellcheck disable=SC2016
grep -q '127.0.0.1:${WEB_PORT:-3300}:3000' "$root/docker-compose.production.yml"
if grep -A20 '^  postgres:' "$root/docker-compose.production.yml" | grep -q 'ports:'; then
  echo "Production PostgreSQL service publishes a host port" >&2; exit 1
fi
grep -q 'AuthType Basic' "$root/deploy/apache/sportsintel.conf.example"
grep -q 'Redirect permanent / https://' "$root/deploy/apache/sportsintel.conf.example"
grep -q 'pg_dump.*--format=custom' "$root/deploy/linux/backup.sh"
grep -q '%Y%m%dT%H%M%SZ' "$root/deploy/linux/backup.sh"
grep -q 'sportsintel-.*\.dump' "$root/deploy/linux/backup.sh"
grep -q 'previous_release_commit' "$root/deploy/linux/rollback.sh"
grep -q 'Invalid Git ref' "$root/deploy/linux/deploy.sh"
grep -q 'RestartCount' "$root/deploy/linux/status.sh"
if grep -Eq 'DATABASE_URL|ADMIN_KEY|POSTGRES_PASSWORD' "$root/deploy/linux/status.sh"; then
  echo "Status script may expose sensitive configuration" >&2; exit 1
fi

metadata_root="$(mktemp -d)"
trap 'rm -rf "$metadata_root"' EXIT
mkdir -p "$metadata_root/shared"
printf '{"deployed_git_commit": "aaaaaaaa", "previous_release_commit": "bbbbbbbb"}\n' \
  >"$metadata_root/shared/deployment.json"
deployed="$(SPORTSINTEL_DEPLOY_ROOT="$metadata_root" bash -c \
  'source "$1"; metadata_value deployed_git_commit' _ "$root/deploy/linux/lib/common.sh")"
previous="$(SPORTSINTEL_DEPLOY_ROOT="$metadata_root" bash -c \
  'source "$1"; metadata_value previous_release_commit' _ "$root/deploy/linux/lib/common.sh")"
[[ "$deployed" == "aaaaaaaa" && "$previous" == "bbbbbbbb" ]] || {
  echo "Rollback metadata parsing failed" >&2; exit 1;
}

if bash -c 'source "$1"; PATH=/definitely/missing; require_command docker' _ \
  "$root/deploy/linux/lib/common.sh" 2>"${TMPDIR:-/tmp}/sportsintel-missing-docker.log"; then
  echo "command validation accepted missing Docker" >&2; exit 1
fi
grep -q 'Required command not found: docker' "${TMPDIR:-/tmp}/sportsintel-missing-docker.log"

if SPORTSINTEL_ENV_FILE=/definitely/missing "$root/deploy/linux/deploy.sh" HEAD 2>"${TMPDIR:-/tmp}/sportsintel-missing-env.log"; then
  echo "deploy.sh accepted a missing environment file" >&2; exit 1
fi
grep -q 'environment file is not readable' "${TMPDIR:-/tmp}/sportsintel-missing-env.log"

if "$root/deploy/linux/smoke-test.sh" --external 2>"${TMPDIR:-/tmp}/sportsintel-auth.log"; then
  echo "external smoke test accepted missing authentication configuration" >&2; exit 1
fi
grep -q 'SPORTSINTEL_PUBLIC_URL is required' "${TMPDIR:-/tmp}/sportsintel-auth.log"

if grep -REn --exclude=validate-deployment.sh '(BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|SPORTSINTEL_ADMIN_KEY=[^r]|POSTGRES_PASSWORD=[^r])' \
  "$root/deploy" "$root/docker-compose.production.yml" "$root/production.env.example"; then
  echo "Potential secret detected in deployment assets" >&2; exit 1
fi
echo "Deployment asset validation passed."
