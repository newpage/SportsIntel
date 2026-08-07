#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=deploy/linux/lib/common.sh
source "$(dirname "$0")/lib/common.sh"

check_only=false; admin_user=""
while (($#)); do
  case "$1" in
    --check-only|--dry-run) check_only=true; shift ;;
    --admin-user) [[ -n "${2:-}" ]] || { echo "--admin-user requires a username" >&2; exit 2; }; admin_user="$2"; shift 2 ;;
    *) echo "Usage: $0 [--check-only] [--admin-user <username>]" >&2; exit 2 ;;
  esac
done

[[ -r /etc/os-release ]] || { echo "Unsupported host: /etc/os-release is missing" >&2; exit 1; }
# shellcheck disable=SC1091
source /etc/os-release
[[ "${ID:-}" == "ubuntu" || "${ID:-}" == "debian" ]] || { echo "Supported hosts are Ubuntu LTS and Debian stable." >&2; exit 1; }

missing=()
for tool in git curl openssl docker apache2ctl htpasswd pg_dump pg_restore python3 flock; do command -v "$tool" >/dev/null 2>&1 || missing+=("$tool"); done
docker compose version >/dev/null 2>&1 || missing+=("docker-compose-plugin")
if $check_only; then
  ((${#missing[@]} == 0)) || { echo "Missing host prerequisites: ${missing[*]}" >&2; exit 1; }
  echo "Host prerequisites are available."
  exit 0
fi

[[ ${EUID} -eq 0 ]] || { echo "install.sh requires root; rerun with sudo." >&2; exit 1; }
if ((${#missing[@]})); then
  echo "Installing required Ubuntu/Debian packages: ${missing[*]}"
  apt-get update -qq
  packages=()
  command -v git >/dev/null 2>&1 || packages+=(git)
  command -v curl >/dev/null 2>&1 || packages+=(curl)
  command -v openssl >/dev/null 2>&1 || packages+=(openssl)
  command -v apache2ctl >/dev/null 2>&1 || packages+=(apache2)
  command -v htpasswd >/dev/null 2>&1 || packages+=(apache2-utils)
  command -v pg_dump >/dev/null 2>&1 || packages+=(postgresql-client)
  command -v pg_restore >/dev/null 2>&1 || packages+=(postgresql-client)
  command -v python3 >/dev/null 2>&1 || packages+=(python3)
  command -v flock >/dev/null 2>&1 || packages+=(util-linux)
  command -v docker >/dev/null 2>&1 || packages+=(docker.io)
  ((${#packages[@]} == 0)) || DEBIAN_FRONTEND=noninteractive apt-get install -y "${packages[@]}"
  if ! docker compose version >/dev/null 2>&1; then
    if apt-cache show docker-compose-v2 >/dev/null 2>&1; then
      DEBIAN_FRONTEND=noninteractive apt-get install -y docker-compose-v2
    elif apt-cache show docker-compose-plugin >/dev/null 2>&1; then
      DEBIAN_FRONTEND=noninteractive apt-get install -y docker-compose-plugin
    else
      echo "Docker Compose v2 is unavailable in configured repositories; configure Docker's supported repository and rerun." >&2; exit 1
    fi
  fi
fi
systemctl enable --now docker
getent group sportsintel >/dev/null || groupadd --system sportsintel
getent group docker >/dev/null || groupadd --system docker
root="$(deployment_root)"
id sportsintel >/dev/null 2>&1 || useradd --system --gid sportsintel --home-dir "$root" --shell /bin/bash sportsintel
usermod --home "$root" --append --groups docker sportsintel
if [[ -n "$admin_user" ]]; then
  id "$admin_user" >/dev/null 2>&1 || { echo "Administrator account does not exist: $admin_user" >&2; exit 1; }
  usermod --append --groups sportsintel "$admin_user"
fi
install -d -o root -g sportsintel -m 2750 "$root"
install -d -o sportsintel -g sportsintel -m 2750 "$root/app" "$root/releases"
install -d -o sportsintel -g sportsintel -m 2770 "$root/shared"
install -d -o sportsintel -g sportsintel -m 2700 "$root/backups"
install -d -o sportsintel -g sportsintel -m 0700 "$root/.docker" "$root/.config"
echo "Host and permissions are prepared. Docker-group membership is root-equivalent."
echo "A new login session is required for new group memberships to take effect."
echo "Firewall and Apache site configuration were not modified."
