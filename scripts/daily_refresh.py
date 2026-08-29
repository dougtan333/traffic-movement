"""
AMIP Daily Data Refresh

Refreshes all daily data sources in the correct order:
  1. Retail fuel prices (Servo Saver API)
  2. Brent crude + AUD/USD exchange rates (EIA + RBA)
  3. AIP Terminal Gate Prices (wholesale, may timeout)

The Bluetooth speed poller runs separately and continuously. This
script stops it around its write-heavy jobs so they are not fighting the
poller for the DuckDB write lock, and starts it again afterwards. That
supervision goes through scripts/service_control.py, so it works under
launchd on the Mac and systemd on the VPS — it used to shell out to
`sudo -n systemctl` directly, which was a silent no-op on macOS.

Usage:
  python scripts/daily_refresh.py          # run once
  python scripts/daily_refresh.py --loop   # run daily at 4am AEST

Data sources refreshed:
  - Retail fuel:  Service VIC Servo Saver (daily snapshot, 24h delayed)
  - Brent crude:  US EIA API (daily spot price, USD/barrel)
  - AUD/USD:      RBA (daily exchange rate)
  - Wholesale:    AIP Terminal Gate Prices (scraped, may be slow)

Not refreshed here (separate cadence):
  - Bluetooth speed:  continuous poller (poll_bluetooth.py --loop)
  - Fuel stations:    monthly (run ingest_fuel_stations.py)
  - Calendar/events:  as needed (run populate_calendar.py)
  - PT/Fleet data:    annual (run ingest_vic_transport.py for vehicle registrations)

Monthly refresh (runs daily but only picks up new data when source publishes):
  - SCATS:    VIC traffic signal volume data (refresh_scats.py, incremental)
  - TIRTL:    VIC vehicle classification + speed (refresh_tirtl.py, file-size check)
  - PT:       VIC public transport patronage (refresh_pt.py, file-size check, 2-month lag)
  - Aviation: BITRE airport traffic, routes, OTP (ingest_aviation.py)
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

sys.path.insert(0, str(SCRIPTS_DIR))
import service_control  # noqa: E402  (needs SCRIPTS_DIR on sys.path first)

# Resolved once: which init system supervises this host, and what it calls the
# Bluetooth poller. launchd on the Mac, systemd on the VPS.
CONTROLLER = service_control.get_controller()
BLUETOOTH_SERVICE = service_control.service_id_for(CONTROLLER, "bluetooth")


def log(msg):
    ts = datetime.now(AEST).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def stop_bluetooth_poller():
    """Stop the Bluetooth poller so write-heavy jobs get the DuckDB write lock.

    Returns True when the supervisor accepted the stop. A failure is logged
    loudly rather than swallowed: the whole point of the stop is that
    archive_speed.py and build_summaries.py are not racing the poller for
    speed.duckdb's WAL lock, so a silent failure corrupts nothing but does
    produce the lock contention this sequencing exists to avoid.

    On macOS the agents carry a KeepAlive PathState guard, so launchd relaunches
    the poller after its 10s ThrottleInterval. The stop buys a clean window at
    the head of each write, not an indefinite shutdown.
    """
    log(f"  Stopping Bluetooth poller ({BLUETOOTH_SERVICE}) for DB writes...")
    try:
        ok = CONTROLLER.stop(BLUETOOTH_SERVICE)
    except Exception as e:
        log(f"  WARNING: could not stop {BLUETOOTH_SERVICE}: {e}")
        ok = False
    if not ok:
        log(f"  WARNING: stop of {BLUETOOTH_SERVICE} did not succeed "
            f"({service_control.describe_state(_service_state())}) — "
            f"DB writes may contend with the poller for the WAL lock")
    time.sleep(2)  # let the poller close its connection before writes begin
    return ok


def start_bluetooth_poller():
    """Start the Bluetooth poller again after the writes are done.

    Returns True when the supervisor accepted the start. A failure here means
    speed polling is down until the watchdog's next 15-minute pass, so it is
    logged as an error rather than a warning.
    """
    log(f"  Restarting Bluetooth poller ({BLUETOOTH_SERVICE})...")
    try:
        ok = CONTROLLER.start(BLUETOOTH_SERVICE)
    except Exception as e:
        log(f"  ERROR: could not start {BLUETOOTH_SERVICE}: {e}")
        ok = False
    if not ok:
        log(f"  ERROR: start of {BLUETOOTH_SERVICE} did not succeed "
            f"({service_control.describe_state(_service_state())}) — "
            f"speed polling is DOWN until the watchdog restarts it")
    return ok


def _service_state():
    """The poller's supervisor state, or STATE_UNKNOWN if the query itself fails."""
    try:
        return CONTROLLER.state(BLUETOOTH_SERVICE)
    except Exception:
        return service_control.STATE_UNKNOWN


def run_script(name, description, args=None, timeout=300):
    """Run a Python script and report success/failure."""
    script = SCRIPTS_DIR / name
    if not script.exists():
        log(f"  SKIP {name} — file not found")
        return False

    log(f"  Running {description}...")
    cmd = [sys.executable, str(script)]
    if args:
        cmd.extend(args)
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True, text=True, timeout=timeout,
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
        log(f"  TIMEOUT {name} (>{timeout}s)")
        return False
    except Exception as e:
        log(f"  ERROR {name}: {e}")
        return False


def refresh_all():
    """Run all daily refresh jobs.
    
    Stops the Bluetooth poller before write-heavy operations to avoid
    DuckDB WAL lock conflicts, restarts it after all writes complete.
    """
    log("=" * 60)
    log("AMIP DAILY REFRESH")
    log("=" * 60)

    # Stop Bluetooth poller to release DB write lock
    stop_bluetooth_poller()

    results = {}

    # 0. Metro core stations — frozen Feb 2026 cohort (DEC-040).
    #    No-op if already materialized; one-time cost on first deploy.
    results["metro_core"] = run_script(
        "materialize_metro_core.py",
        "Metro core station cohort (no-op if already materialized)"
    )

    # 1. Retail fuel prices (AM snapshot — PM runs separately at 5pm)
    results["retail_fuel"] = run_script(
        "poll_fuel_prices.py",
        "Retail fuel prices (Servo Saver)",
        args=["--period", "AM"]
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

    # 4a. SCATS traffic counts — incremental download + ingest from VIC portal
    #     Handles its own summary + Parquet updates internally.
    results["scats"] = run_script(
        "refresh_scats.py",
        "SCATS traffic counts (incremental)"
    )

    # 4b. TIRTL vehicle classification + speed — monthly ZIPs from VIC portal
    #     Uses file-size comparison to detect updated files. ~100MB per month.
    results["tirtl"] = run_script(
        "refresh_tirtl.py",
        "TIRTL vehicle classification + speed",
        timeout=600
    )

    # 4c. PT patronage — monthly CSVs from VIC portal (2-month lag)
    #     File-size comparison, full table replace. Small files (~10KB).
    results["pt_patronage"] = run_script(
        "refresh_pt.py",
        "PT patronage (monthly totals + day-type)"
    )

    # 5. Append new days to summary tables (after any data ingestion)
    results["summaries"] = run_script(
        "build_summaries.py",
        "Summary tables (append new days)",
        args=["--append"]
    )

    # 6. Speed data Parquet archive (incremental — only new data since last archive)
    results["speed_archive"] = run_script(
        "archive_speed.py",
        "Speed data Parquet archive (incremental)"
    )

    # 7. Database backup — runs last, after all data updates
    results["backup"] = run_script(
        "backup_db.py",
        "Database backup (timestamped copy)"
    )

    # Restart Bluetooth poller now that all writes are done
    start_bluetooth_poller()

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
                        help="Run daily at 4am AEST")
    args = parser.parse_args()

    if not args.loop:
        success = refresh_all()
        sys.exit(0 if success else 1)

    # Loop mode: run full refresh at 4am AEST, fuel-only at 5pm AEST
    log("Starting daily refresh loop (4am full + 5pm fuel)")
    while True:
        now = datetime.now(AEST)

        # Calculate next event: 4am (full) or 5pm (fuel PM)
        target_4am = now.replace(hour=4, minute=0, second=0, microsecond=0)
        target_5pm = now.replace(hour=17, minute=0, second=0, microsecond=0)
        if now >= target_4am:
            target_4am += timedelta(days=1)
        if now >= target_5pm:
            target_5pm += timedelta(days=1)

        # Pick whichever is sooner
        if target_5pm < target_4am:
            target = target_5pm
            job_type = "fuel_pm"
        else:
            target = target_4am
            job_type = "full"

        wait_secs = (target - now).total_seconds()
        label = "FULL REFRESH" if job_type == "full" else "FUEL PM ONLY"
        log(f"Next: {label} at {target.strftime('%Y-%m-%d %H:%M')} AEST ({wait_secs/3600:.1f}h)")
        time.sleep(wait_secs)

        if job_type == "full":
            refresh_all()
        else:
            # PM fuel poll only — stop bluetooth for write lock
            log("=" * 60)
            log("FUEL PM SNAPSHOT")
            log("=" * 60)
            stop_bluetooth_poller()
            run_script("poll_fuel_prices.py", "Retail fuel prices (PM)",
                       args=["--period", "PM"])
            start_bluetooth_poller()
            log("=" * 60)


if __name__ == "__main__":
    main()
