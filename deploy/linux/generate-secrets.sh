#!/usr/bin/env bash
set -euo pipefail
command -v openssl >/dev/null 2>&1 || { echo "openssl is required" >&2; exit 1; }
mode=""; target=""; force=false
while (($#)); do
  case "$1" in
    --print) mode=print; shift ;;
    --env-file) mode="file"; target="${2:-}"; [[ -n "$target" ]] || { echo "--env-file requires a path" >&2; exit 2; }; shift 2 ;;
    --force) force=true; shift ;;
    *) echo "Usage: $0 (--print | --env-file <path>) [--force]" >&2; exit 2 ;;
  esac
done
[[ -n "$mode" ]] || { echo "Choose --print or --env-file <path>" >&2; exit 2; }
admin_key="$(openssl rand -hex 32)"; postgres_password="$(openssl rand -hex 32)"
content="SPORTSINTEL_ADMIN_KEY=$admin_key
POSTGRES_PASSWORD=$postgres_password"
if [[ "$mode" == "print" ]]; then
  printf '%s\n' "$content"
else
  [[ ! -e "$target" || "$force" == true ]] || { echo "Refusing to overwrite existing file without --force: $target" >&2; exit 1; }
  umask 077; printf '%s\n' "$content" >"$target"; chmod 600 "$target"
  echo "Secrets written with mode 600: $target"
fi
echo "Apache Basic Authentication requires separate credentials." >&2
