#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=deploy/linux/lib/common.sh
source "$(dirname "$0")/lib/common.sh"
yes=false; remove_files=false
while (($#)); do
  case "$1" in --yes) yes=true ;; --remove-files) remove_files=true ;; *) echo "Usage: $0 [--yes] [--remove-files]" >&2; exit 2 ;; esac; shift
done
require_tools docker
load_environment
project="${COMPOSE_PROJECT_NAME:-sportsintel}"
[[ "$project" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] || { echo "Invalid COMPOSE_PROJECT_NAME" >&2; exit 1; }
echo "This removes only Compose project '$project': its containers, networks, and declared volumes."
echo "It will not run docker system prune or remove similarly named projects such as sportsintel-ai."
$remove_files && echo "It will also remove deployment files under $(deployment_root) after the Compose project is down."
if ! $yes; then read -r -p "Type RESET-$project to continue: " answer; [[ "$answer" == "RESET-$project" ]] || { echo "Reset cancelled."; exit 1; }; fi
compose down --volumes --remove-orphans
if $remove_files; then
  root="$(deployment_root)"
  [[ "$root" == /opt/sportsintel || "$root" == /tmp/sportsintel-* ]] || { echo "Refusing unsafe deployment root: $root" >&2; exit 1; }
  rm -rf -- "$root/app" "$root/shared" "$root/backups" "$root/releases" "$root/.docker"
  echo "Removed the explicitly listed SportsIntel deployment directories under $root."
fi
echo "Preview project '$project' reset completed."
