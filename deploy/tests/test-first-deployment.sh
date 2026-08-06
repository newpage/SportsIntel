#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=deploy/linux/lib/common.sh
source "$root/deploy/linux/lib/common.sh"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

echo "Testing URL-safe secret generation"
"$root/deploy/linux/generate-secrets.sh" --env-file "$tmp/secrets.env" >/dev/null 2>&1
[[ "$(file_mode "$tmp/secrets.env")" == "600" ]]
grep -Eq '^SPORTSINTEL_ADMIN_KEY=[0-9a-f]{64}$' "$tmp/secrets.env"
grep -Eq '^POSTGRES_PASSWORD=[0-9a-f]{64}$' "$tmp/secrets.env"
if "$root/deploy/linux/generate-secrets.sh" --env-file "$tmp/secrets.env" >/dev/null 2>&1; then echo "secret helper overwrote a file" >&2; exit 1; fi

echo "Testing DATABASE_URL validation"
POSTGRES_USER=sportsintel; POSTGRES_PASSWORD=0123456789abcdef
DATABASE_URL="postgresql://sportsintel:${POSTGRES_PASSWORD}@postgres:5432/sportsintel"
validate_database_url
DATABASE_URL='postgresql://sportsintel:abc/def+ghi@postgres:5432/sportsintel'
if message="$(validate_database_url 2>&1)"; then echo "malformed Base64 password was accepted" >&2; exit 1; fi
[[ "$message" == *"DATABASE_URL is invalid. Use a URL-safe password or percent-encode it."* ]]

echo "Testing PostgreSQL delayed readiness and timeout"
counter="$tmp/readiness-count"; echo 0 >"$counter"
container_health() { local count; count="$(cat "$counter")"; count=$((count + 1)); echo "$count" >"$counter"; if ((count >= 3)); then echo healthy; else echo starting; fi; }
compose() { [[ " $* " == *" exec "* ]] && return 0; return 0; }
sleep() { :; }
POSTGRES_USER=sportsintel POSTGRES_DB=sportsintel SPORTSINTEL_POSTGRES_TIMEOUT_SECONDS=10 wait_for_postgres >/dev/null
container_health() { echo starting; }
if POSTGRES_USER=sportsintel POSTGRES_DB=sportsintel SPORTSINTEL_POSTGRES_TIMEOUT_SECONDS=2 wait_for_postgres >"$tmp/timeout.log" 2>&1; then echo "PostgreSQL timeout was not enforced" >&2; exit 1; fi
grep -q 'readiness timed out' "$tmp/timeout.log"

echo "Testing project-scoped reset"
mkdir -p "$tmp/fakebin"; touch "$tmp/sportsintel-ai_postgres_data"
cat >"$tmp/fakebin/docker" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$SPORTSINTEL_DOCKER_CALLS"
SH
chmod +x "$tmp/fakebin/docker"
PATH="$tmp/fakebin:$PATH" SPORTSINTEL_DOCKER_CALLS="$tmp/docker.calls" \
  SPORTSINTEL_ENV_FILE="$tmp/secrets.env" COMPOSE_PROJECT_NAME=sportsintel \
  "$root/deploy/linux/reset-preview.sh" --yes >/dev/null
grep -q -- '--project-name sportsintel' "$tmp/docker.calls"
grep -q -- 'down --volumes --remove-orphans' "$tmp/docker.calls"
[[ -e "$tmp/sportsintel-ai_postgres_data" ]]
grep -q 'load_environment' "$root/deploy/linux/reset-preview.sh"

echo "Testing installer permissions and transactional promotion"
grep -q 'sportsintel.*docker' "$root/deploy/linux/install.sh"
grep -q '2770.*shared' "$root/deploy/linux/install.sh"
grep -q '0700.*\.docker' "$root/deploy/linux/install.sh"
grep -q '0700.*\.docker.*\.config' "$root/deploy/linux/install.sh"
grep -q 'DOCKER_CONFIG=.*docker_home' "$root/deploy/linux/preflight.sh"
grep -q 'release.env.candidate' "$root/deploy/linux/deploy.sh"
grep -q 'trap failure_handler' "$root/deploy/linux/deploy.sh"
grep -q 'SPORTSINTEL_TEST_FAIL_PHASE' "$root/deploy/linux/deploy.sh"
# Match the literal candidate variable in deploy.sh.
# shellcheck disable=SC2016
promotion_line="$(grep -n 'mv "$candidate"' "$root/deploy/linux/deploy.sh" | cut -d: -f1)"
smoke_line="$(grep -n 'smoke-test.sh' "$root/deploy/linux/deploy.sh" | tail -1 | cut -d: -f1)"
[[ "$promotion_line" -gt "$smoke_line" ]]
echo "First-deployment hardening tests passed."
