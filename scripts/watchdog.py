"""
AMIP Watchdog — Service health + data freshness monitor

Runs every 15 minutes via systemd timer. Checks:
  1. All three services are active (api, bluetooth, refresh)
  2. Data freshness for each source against expected cadence
  3. API endpoints return 200 with valid JSON
  4. Frontend is reachable

Restarts dead services automatically. Logs all results to
stdout (captured by journalctl) and optionally to a log file.

Usage:
  python scripts/watchdog.py              # check + auto-restart
  python scripts/watchdog.py --check-only # check without restarting
  python scripts/watchdog.py --verbose    # detailed output

Designed to run as: systemd timer (every 15 min)
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

import duckdb
import service_control

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AMIP_DB = PROJECT_ROOT / "db" / "amip.duckdb"
SPEED_DB = PROJECT_ROOT / "db" / "speed.duckdb"
AEST = timezone(timedelta(hours=10))

API_BASE = "https://api.melbtraffic.com"
FRONTEND_URL = "https://melbtraffic.com"

# Service identifiers now live in scripts/service_control.py (SERVICE_IDS),
# which maps them per platform. Nothing here needs to know the names.

# Data freshness thresholds (max age before considered stale)
FRESHNESS = {
    # The VIC bluetooth feed publishes a new ts_interval every ~30-36 min, not every 5 —
    # measured over 7 days of distinct intervals (modal gaps 30-36 min, worst normal 36).
    # The pollers run every 5 min and store all 4,711 links per new interval; a tighter
    # threshold than the source cadence WARNs on ~half of all runs regardless of health.
    "speed_observations":     {"db": "speed",  "max_age_hours": 1.0,   "query": "SELECT max(ts_interval) FROM speed_observations"},
    "fuel_prices":            {"db": "main",   "max_age_hours": 36,    "query": "SELECT max(snapshot_date) FROM fuel_prices"},
    "wholesale_prices":       {"db": "main",   "max_age_hours": 72,    "query": "SELECT max(date) FROM wholesale_prices"},
    "daily_station_summary":  {"db": "main",   "max_age_hours": 1080,  "query": "SELECT max(day) FROM daily_station_summary"},  # ~45 days (monthly source)
}

# API endpoints to probe (must return 200 with JSON body)
API_PROBES = [
    "/api/health",
    "/api/speed/snapshot",
    "/api/monitor/",
    "/api/fuel/state-average",
]

class WatchdogResult:
    def __init__(self):
        self.checks = []
        self.problems = []

    def ok(self, name, detail=""):
        self.checks.append(("OK", name, detail))

    def warn(self, name, detail=""):
        self.checks.append(("WARN", name, detail))
        self.problems.append(("WARN", name, detail))

    def fail(self, name, detail=""):
        self.checks.append(("FAIL", name, detail))
        self.problems.append(("FAIL", name, detail))

    @property
    def healthy(self):
        return len(self.problems) == 0


def now_aest():
    return datetime.now(AEST)


def log(msg):
    ts = now_aest().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")

def check_services(result, auto_restart=True):
    """Check every AMIP service is running. Restart any that are not.

    Service supervision is delegated to scripts/service_control.py so this
    function reads the same on the VPS (systemd) and the Mac (launchd).

    The failure detail carries the supervisor's state rather than a flat
    "not running", because "the agent was never loaded — T9 was not mounted at
    login" and "the process keeps dying" need different responses from a human
    and used to log identically (finding I7).
    """
    controller = service_control.get_controller()
    for svc in service_control.service_ids(controller):
        try:
            state = controller.state(svc)
        except Exception as e:
            result.fail(f"service/{svc}", f"check failed: {e}")
            continue

        if state == service_control.STATE_RUNNING:
            result.ok(f"service/{svc}", "active")
            continue

        detail = f"not running — {service_control.describe_state(state)}"
        result.fail(f"service/{svc}", detail)
        if not auto_restart:
            continue

        log(f"  {svc}: {detail}")
        log(f"  Restarting {svc}...")
        try:
            started = controller.start(svc)
            time.sleep(3)  # give the supervisor a moment to report the new state
            after = controller.state(svc)
            if after == service_control.STATE_RUNNING:
                log(f"  {svc} restarted successfully")
            else:
                # `started` is the restart command's own exit status; `after` is
                # what the supervisor says a moment later. Both are logged
                # because a start that reports success but leaves the service
                # down is a different fault from one that never ran.
                log(f"  {svc} FAILED to restart "
                    f"(start command {'succeeded' if started else 'failed'}; "
                    f"now {service_control.describe_state(after)})")
        except Exception as e:
            log(f"  {svc} restart error: {e}")

def check_data_freshness(result):
    """Check each data source is within its expected freshness window."""
    now = now_aest()
    connections = {}

    for source, cfg in FRESHNESS.items():
        db_key = cfg["db"]
        db_path = SPEED_DB if db_key == "speed" else AMIP_DB

        try:
            if db_key not in connections:
                connections[db_key] = duckdb.connect(str(db_path), read_only=True)
            con = connections[db_key]

            row = con.execute(cfg["query"]).fetchone()
            latest = row[0] if row else None

            if latest is None:
                result.warn(f"data/{source}", "no data found")
                continue

            # Convert to datetime for age calculation
            if hasattr(latest, 'hour'):  # timestamp
                latest_dt = latest.replace(tzinfo=AEST) if latest.tzinfo is None else latest
            else:  # date
                latest_dt = datetime.combine(latest, datetime.min.time()).replace(tzinfo=AEST)

            age_hours = (now - latest_dt).total_seconds() / 3600
            max_age = cfg["max_age_hours"]

            if age_hours <= max_age:
                result.ok(f"data/{source}", f"latest={latest}, age={age_hours:.1f}h")
            elif age_hours <= max_age * 2:
                result.warn(f"data/{source}", f"latest={latest}, age={age_hours:.1f}h (threshold={max_age}h)")
            else:
                result.fail(f"data/{source}", f"latest={latest}, age={age_hours:.1f}h (threshold={max_age}h)")

        except Exception as e:
            result.warn(f"data/{source}", f"query error: {e}")

    for con in connections.values():
        try: con.close()
        except: pass

def check_api_endpoints(result):
    """Probe API endpoints to verify they return 200 + valid JSON."""
    if not HAS_REQUESTS:
        result.warn("api/probe", "requests library not installed — skipping API checks")
        return

    for path in API_PROBES:
        url = f"{API_BASE}{path}"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                try:
                    data = r.json()
                    # Check for error responses that return 200
                    if isinstance(data, dict) and data.get("status") == "error":
                        result.warn(f"api{path}", f"200 but error response: {data.get('message', '')[:80]}")
                    else:
                        cache_status = r.headers.get("X-Cache", "no-cache-header")
                        result.ok(f"api{path}", f"200 OK [{cache_status}]")
                except ValueError:
                    result.warn(f"api{path}", "200 but not valid JSON")
            else:
                result.fail(f"api{path}", f"HTTP {r.status_code}")
        except requests.exceptions.Timeout:
            result.fail(f"api{path}", "timeout (10s)")
        except requests.exceptions.ConnectionError as e:
            result.fail(f"api{path}", f"connection error: {e}")
        except Exception as e:
            result.fail(f"api{path}", f"error: {e}")

def check_frontend(result):
    """Verify frontend is reachable on Cloudflare Pages."""
    if not HAS_REQUESTS:
        return

    try:
        r = requests.get(FRONTEND_URL, timeout=10)
        if r.status_code == 200 and "<html" in r.text.lower()[:500]:
            result.ok("frontend", f"200 OK ({len(r.text):,} bytes)")
        else:
            result.warn("frontend", f"HTTP {r.status_code}, content may be wrong")
    except Exception as e:
        result.fail("frontend", f"unreachable: {e}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="AMIP Watchdog")
    parser.add_argument("--check-only", action="store_true", help="Check without restarting services")
    parser.add_argument("--verbose", action="store_true", help="Show all checks, not just problems")
    args = parser.parse_args()

    result = WatchdogResult()

    log("AMIP Watchdog running")

    check_services(result, auto_restart=not args.check_only)
    check_data_freshness(result)
    check_api_endpoints(result)
    check_frontend(result)

    # Output
    if args.verbose:
        for status, name, detail in result.checks:
            log(f"  {status:4s} {name}: {detail}")
    elif result.problems:
        for status, name, detail in result.problems:
            log(f"  {status:4s} {name}: {detail}")

    if result.healthy:
        log(f"ALL OK ({len(result.checks)} checks passed)")
    else:
        ok_count = len(result.checks) - len(result.problems)
        log(f"ISSUES: {len(result.problems)} problem(s), {ok_count} OK")

    return 0 if result.healthy else 1


if __name__ == "__main__":
    sys.exit(main())
