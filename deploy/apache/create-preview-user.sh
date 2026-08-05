#!/usr/bin/env bash
set -euo pipefail
command -v htpasswd >/dev/null 2>&1 || { echo "htpasswd is required (install apache2-utils)." >&2; exit 1; }
[[ ${EUID} -eq 0 ]] || { echo "Run this script with sudo." >&2; exit 1; }
user="${1:-}"; file="${SPORTSINTEL_HTPASSWD_FILE:-/etc/apache2/sportsintel-preview.htpasswd}"
[[ "$user" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "Usage: $0 <preview-username>" >&2; exit 2; }
if [[ -f "$file" ]]; then htpasswd "$file" "$user"; else htpasswd -c "$file" "$user"; fi
chown root:www-data "$file"; chmod 640 "$file"
echo "Preview user updated in $file; password was not echoed."
