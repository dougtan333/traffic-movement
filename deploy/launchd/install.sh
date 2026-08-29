#!/usr/bin/env bash
# install.sh — Symlink the generated LaunchAgents into ~/Library/LaunchAgents
#
# Symlinks rather than copies, so a regenerate is picked up without a reinstall
# and the plists stay version-controlled in the repo (D7).
#
# Usage: bash deploy/launchd/install.sh [--load]
#   --load also bootstraps each agent into the current GUI domain.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$HOME/Library/LaunchAgents"
DOMAIN="gui/$(id -u)"

mkdir -p "$AGENT_DIR"

for plist in "$HERE"/com.amip.*.plist; do
    label="$(basename "$plist" .plist)"
    ln -sfn "$plist" "$AGENT_DIR/$label.plist"
    echo "  linked $label"

    if [[ "${1:-}" == "--load" ]]; then
        launchctl bootout "$DOMAIN/$label" 2>/dev/null || true
        launchctl bootstrap "$DOMAIN" "$AGENT_DIR/$label.plist"
        echo "  bootstrapped $label"
    fi
done

echo
echo "Done. Check status with: launchctl list | grep com.amip"
