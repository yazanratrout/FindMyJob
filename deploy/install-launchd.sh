#!/usr/bin/env bash
# Render the launchd plist templates with this checkout's paths and load them.
# Usage:  bash deploy/install-launchd.sh [--server]
#   (without --server, only the daily fallback job is installed)
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$REPO/.venv/bin/python"
AGENTS="$HOME/Library/LaunchAgents"
mkdir -p "$AGENTS" "$REPO/data/logs"

render() {
  local name="$1"
  sed -e "s|__REPO__|$REPO|g" -e "s|__VENV_PYTHON__|$VENV_PYTHON|g" \
    "$REPO/deploy/$name.template" > "$AGENTS/$name"
  launchctl unload "$AGENTS/$name" 2>/dev/null || true
  launchctl load "$AGENTS/$name"
  echo "loaded $AGENTS/$name"
}

render com.findmyjob.daily.plist
if [[ "${1:-}" == "--server" ]]; then
  render com.findmyjob.server.plist
fi
echo "Done. Check with: launchctl list | grep findmyjob"
