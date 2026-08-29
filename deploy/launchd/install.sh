#!/usr/bin/env bash
# install.sh — Copy the generated LaunchAgents into ~/Library/LaunchAgents
#
# COPIES rather than symlinks. The repo lives on the external T9 volume, and a
# symlink into it dangles whenever T9 is not mounted. Measured: `launchctl
# bootstrap` on a dangling symlink fails with "Bootstrap failed: 5:
# Input/output error" and launchd does NOT retry — so a reboot where login wins
# the race against diskarbitrationd mounting T9 leaves every agent absent, with
# no PathState guard to help (the guard lives inside the plist, which could not
# be read) and no watchdog to self-heal (it is on T9 too). Copies live on the
# internal, FileVault-protected disk and are always readable at login.
#
# The cost of copying: a regenerate is NOT picked up automatically.
# ALWAYS run this script after `python3 deploy/launchd/generate.py`, then
# bootout/bootstrap the affected agents for the new plist to take effect.
#
# The plists stay version-controlled in deploy/launchd/ (D7) — only the
# propagation mechanism changed.
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
    # -f so an existing symlink from a previous install is replaced by a real
    # file rather than written through to the target on T9.
    rm -f "$AGENT_DIR/$label.plist"
    cp "$plist" "$AGENT_DIR/$label.plist"
    echo "  copied $label"

    if [[ "${1:-}" == "--load" ]]; then
        launchctl bootout "$DOMAIN/$label" 2>/dev/null || true
        launchctl bootstrap "$DOMAIN" "$AGENT_DIR/$label.plist"
        echo "  bootstrapped $label"
    fi
done

echo
echo "Done. Check status with: launchctl list | grep com.amip"
echo "Remember: re-run this script after every generate.py, then bootout/bootstrap."
