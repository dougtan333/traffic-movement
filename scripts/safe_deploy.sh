#!/usr/bin/env bash
# safe_deploy.sh — WAL-safe deployment for AMIP
# Always use this script instead of raw systemctl restarts.
# Usage: sudo /opt/amip/scripts/safe_deploy.sh [--pull]
#
# LINUX VPS ONLY. Every path here is /opt/amip and every restart is systemctl,
# neither of which exists on the Mac. It is left as-is because it belongs to the
# VPS, which Task 14 decommissions; the Mac equivalent is
# `deploy/launchd/install.sh --load` plus `launchctl bootout`/`bootstrap`, and
# service state is queried through scripts/service_control.py. The guard below
# stops it half-executing if it is ever run on the wrong machine.

set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "safe_deploy.sh is for the Linux VPS only (systemd + /opt/amip)." >&2
    echo "On the Mac use deploy/launchd/install.sh and launchctl instead." >&2
    exit 1
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date '+%H:%M:%S')] WARNING:${NC} $1"; }

DB=/opt/amip/db/amip.duckdb
WAL=/opt/amip/db/amip.duckdb.wal

log "1/6  Stopping Bluetooth poller..."
sudo systemctl stop amip-bluetooth || warn "Poller was not running"
sleep 2

log "2/6  Stopping daily refresh..."
sudo systemctl stop amip-refresh 2>/dev/null || true
sleep 1

log "3/6  Stopping API..."
sudo systemctl stop amip-api || warn "API was not running"
sleep 1

log "4/6  Clearing WAL file..."
if [ -f "$WAL" ]; then
    rm -f "$WAL"
    log "     WAL removed ($(basename $WAL))"
else
    log "     No WAL file present — clean state"
fi

# Optional git pull
if [[ "${1:-}" == "--pull" ]]; then
    log "     Pulling latest code..."
    cd /opt/amip && git pull
fi

log "5/6  Starting API..."
sudo systemctl start amip-api
sleep 2

# Verify API is responding
if curl -sf http://127.0.0.1:8000/api/speed/trend > /dev/null 2>&1; then
    log "     API health check passed"
else
    warn "API health check failed — check logs: journalctl -u amip-api -n 20"
fi

log "6/6  Starting Bluetooth poller + refresh..."
sudo systemctl start amip-bluetooth
sudo systemctl start amip-refresh 2>/dev/null || true

sleep 3
# Final status
log "Deploy complete. Service status:"
echo "  API:       $(systemctl is-active amip-api)"
echo "  Bluetooth: $(systemctl is-active amip-bluetooth)"
echo "  Refresh:   $(systemctl is-active amip-refresh 2>/dev/null || echo 'n/a')"
