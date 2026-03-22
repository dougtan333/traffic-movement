"""
AMIP Daily Data Refresh

Refreshes all daily data sources in the correct order:
  1. Retail fuel prices (Servo Saver API)
  2. Brent crude + AUD/USD exchange rates (EIA + RBA)
  3. AIP Terminal Gate Prices (wholesale, may timeout)

The Bluetooth speed poller runs separately and continuously —
this script does NOT touch it. These scripts use connect/disconnect
per operation so they coexist with the poller's write lock pattern.

Usage:
  python scripts/daily_refresh.py          # run once
  python scripts/daily_refresh.py --loop   # run daily at 7am AEST

Data sources refreshed:
  - Retail fuel:  Service VIC Servo Saver (daily snapshot, 24h delayed)
  - Brent crude:  US EIA API (daily spot price, USD/barrel)
  - AUD/USD:      RBA (daily exchange rate)
  - Wholesale:    AIP Terminal Gate Prices (scraped, may be slow)

Not refreshed here (separate cadence):
  - VIC SCATS counts: monthly ZIP download (run ingest_vic_counts.py)
  - Bluetooth speed:  continuous poller (poll_bluetooth.py --loop)
  - TIRTL data:       as released (run ingest_tirtl.py)
  - Fuel stations:    monthly (run ingest_fuel_stations.py)
  - Calendar/events:  as needed (run populate_calendar.py)
  - PT/Fleet data:    annual (run ingest_vic_transport.py)

Monthly refresh (runs daily but only picks up new data when BITRE publishes):
  - Aviation:  BITRE airport traffic, routes, OTP (ingest_aviation.py)
"""

import os
import sys
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)
AEST = timezone(timedelta(hours=10))


def log(msg):
    ts = datetime.now(AEST).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def run_script(name, description):
    """Run a Python script and report success/failure."""
    script = SCRIPTS_DIR / name
    if not script.exists():
        log(f"  SKIP {name} — file not found")
        return False

    log(f"  Running {description}...")
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(PROJECT_ROOT),
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            # Print last few lines of output for summary
            lines = result.stdout.strip().splitlines()
            for line in lines[-5:]:
                log(f"    {line}")
            log(f"  OK {name}")
            return True
        else:
            log(f"  FAIL {name} (exit {result.returncode})")
            for line in (result.stderr or result.stdout).strip().splitlines()[-3:]:
                log(f"    {line}")
            return False
    except subprocess.TimeoutExpired:
        log(f"  TIMEOUT {name} (>300s)")
        return False
    except Exception as e:
        log(f"  ERROR {name}: {e}")
        return False


def refresh_all():
    """Run all daily refresh jobs."""
    log("=" * 60)
    log("AMIP DAILY REFRESH")
    log("=" * 60)

    results = {}

    # 1. Retail fuel prices
    results["retail_fuel"] = run_script(
        "poll_fuel_prices.py",
        "Retail fuel prices (Servo Saver)"
    )

    # 2. Brent crude + FX rates
    results["brent_fx"] = run_script(
        "refresh_brent.py",
        "Brent crude + AUD/USD (EIA + RBA)"
    )

    # 3. AIP wholesale (may timeout — non-critical)
    results["wholesale"] = run_script(
        "ingest_wholesale_prices.py",
        "AIP Terminal Gate Prices (wholesale)"
    )

    # 4. Aviation — BITRE airport traffic, routes, OTP
    #    Monthly source, but safe to run daily (idempotent full refresh, ~10s)
    results["aviation"] = run_script(
        "ingest_aviation.py",
        "BITRE aviation data (airports, routes, OTP)"
    )

    # Summary
    log("=" * 60)
    ok = sum(1 for v in results.values() if v)
    total = len(results)
    log(f"DONE: {ok}/{total} jobs succeeded")
    for name, success in results.items():
        status = "OK" if success else "FAILED"
        log(f"  {name}: {status}")
    log("=" * 60)

    return all(results.values())


def main():
    parser = argparse.ArgumentParser(description="AMIP daily data refresh")
    parser.add_argument("--loop", action="store_true",
                        help="Run daily at 7am AEST")
    args = parser.parse_args()

    if not args.loop:
        success = refresh_all()
        sys.exit(0 if success else 1)

    # Loop mode: run at 7am AEST daily
    log("Starting daily refresh loop (7am AEST)")
    while True:
        now = datetime.now(AEST)
        # Calculate next 7am
        target = now.replace(hour=7, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        wait_secs = (target - now).total_seconds()
        log(f"Next refresh at {target.strftime('%Y-%m-%d %H:%M')} AEST ({wait_secs/3600:.1f}h)")
        time.sleep(wait_secs)
        refresh_all()


if __name__ == "__main__":
    main()
