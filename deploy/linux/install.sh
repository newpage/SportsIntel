#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=deploy/linux/lib/common.sh
source "$(dirname "$0")/lib/common.sh"

check_only=false
[[ "${1:-}" == "--check-only" || "${1:-}" == "--dry-run" ]] && check_only=true
missing=()
for tool in git curl docker apache2ctl htpasswd pg_dump pg_restore; do command -v "$tool" >/dev/null 2>&1 || missing+=("$tool"); done
docker compose version >/dev/null 2>&1 || missing+=("docker-compose-plugin")
if ((${#missing[@]})); then
  echo "Missing host prerequisites: ${missing[*]}" >&2
  echo "Install them with the supported package manager before continuing." >&2
  exit 1
fi
echo "Host prerequisites are available. Docker group membership grants root-equivalent access."
$check_only && exit 0
root="$(deployment_root)"
echo "Will create $root/{app,shared,backups,releases} and group sportsintel."
[[ ${EUID} -eq 0 ]] || { echo "install.sh requires root; rerun with sudo or use --check-only" >&2; exit 1; }
getent group sportsintel >/dev/null || groupadd --system sportsintel
id sportsintel >/dev/null 2>&1 || useradd --system --gid sportsintel --home-dir "$root" --shell /usr/sbin/nologin sportsintel
install -d -o sportsintel -g sportsintel -m 0750 "$root/app" "$root/releases"
install -d -o root -g sportsintel -m 0750 "$root/shared"
install -d -o sportsintel -g sportsintel -m 0700 "$root/backups"
echo "Directories prepared. Firewall and Apache were not modified. Review the runbook before enabling either."
