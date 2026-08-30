#!/usr/bin/env python3
"""
check_refresh.py — post-mortem on the 4am full refresh.

WHY THIS EXISTS
    The VPS→Mac migration's last open gate is whether the 11-job full refresh
    completes unattended on the Mac. It has never done so: the 2026-08-30
    04:30 run was 0/11 (every job hit its exact timeout because the wedged API
    still held amip.duckdb), and the only successful run since was a manual
    13:31 re-run that got 9/11. This script reads the outcome of the next
    scheduled run and says plainly whether the gate is passed, so the answer is
    waiting on screen rather than needing to be dug out of a log.

WHAT IT CHECKS
    1. The most recent FULL REFRESH block in the refresh log — the DONE tally
       and every per-job status line.
    2. That a database backup landed, newer than the run's own start time.
    3. That all seven LaunchAgents are still loaded afterwards.
    4. That the public API answers through the tunnel.
    5. That the Bluetooth poller has no new overnight gap. The refresh stops
       and restarts the poller to take the DB write lock, so a failure to
       restart it would otherwise go unnoticed until the data thinned out.

WHAT COUNTS AS SUCCESS
    9/11 or better, with the only failures being the two jobs already known to
    be broken at source and unrelated to the migration:
      wholesale     — the scrape has returned nulls since 2026-08-03, ~4 weeks
                      before cutover, while the VPS was still serving.
      pt_patronage  — upstream 404/403 on both opendata.transport.vic.gov.au
                      resource URLs. Dead at source; fails identically on the VPS.
    Any OTHER job failing is a real regression and flips the verdict to FAIL.

CONNECTS TO
    scripts/daily_refresh.py   — produces the log this parses (its `DONE: n/total
                                 jobs succeeded` line and per-job `name: OK|FAILED`).
    ~/Library/LaunchAgents/com.amip.refresh-check.plist — fires this at 04:15.
    .superpowers/sdd/2026-08-29-vps-to-mac-migration/progress.md — the ledger
                                 this closes out Task 13 Step 4 in.

USAGE
    venv/bin/python3 scripts/check_refresh.py            # check, notify, log
    venv/bin/python3 scripts/check_refresh.py --no-notify  # log only (for testing)
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

PROJECT = Path("/Volumes/T9/Projects/Traffic Movement")
LOG_DIR = Path.home() / "Library/Logs/amip"
REFRESH_LOG = LOG_DIR / "com.amip.refresh.log"
REPORT_LOG = LOG_DIR / "refresh-check.log"
BACKUP_DIR = PROJECT / "db/backups"
SPEED_DB = PROJECT / "db/speed.duckdb"

HEALTH_URL = "https://api.melbtraffic.com/api/health"

# Cloudflare 403s urllib's default "Python-urllib/3.x" user agent, so the probe
# has to identify itself as something ordinary or it reports a false outage.
USER_AGENT = "amip-refresh-check/1.0"

# The banner daily_refresh.py prints for a full run (its source line 166).
# Deliberately not "FULL REFRESH" — that string only appears in the "Next:" line.
FULL_BANNER = "AMIP DAILY REFRESH"

# The seven agents that must survive a refresh. The refresh deliberately stops
# and restarts com.amip.bluetooth, so it is included precisely to catch a
# restart that did not happen.
AGENTS = [
    "com.amip.api", "com.amip.bluetooth", "com.amip.bluetooth-archive",
    "com.amip.refresh", "com.amip.tunnel", "com.amip.filevault",
    "com.amip.watchdog",
]

# Failures that are expected and NOT migration regressions — see module docstring.
KNOWN_BAD = {"wholesale", "pt_patronage"}

# The feed publishes a new interval every ~30-36 min (measured over 7 days), so
# anything beyond an hour is a genuine stall rather than normal cadence.
MAX_GAP_MIN = 60

TS = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")


# --------------------------------------------------------------------------
# Log parsing
# --------------------------------------------------------------------------

def last_full_refresh(log_path: Path) -> tuple[list[str], datetime | None]:
    """Return the lines of the most recent full-refresh block, and its start time.

    daily_refresh.py banners the full run with "AMIP DAILY REFRESH" (source line
    166) and the evening fuel-only run with "FUEL PM SNAPSHOT" (line 305), each
    between two rules of '='. Note the banner text is NOT the same string as the
    "FULL REFRESH" label used in the loop's "Next:" line — matching on that
    instead finds nothing. We slice from the last full-run banner to the end of
    file, which is the whole run plus whatever the loop logged afterwards.
    """
    if not log_path.exists():
        return [], None

    lines = log_path.read_text(errors="replace").splitlines()
    start_idx = None
    for i, line in enumerate(lines):
        if line.rstrip().endswith(FULL_BANNER):
            start_idx = i

    if start_idx is None:
        return [], None

    block = lines[start_idx:]
    started = None
    m = TS.match(block[0])
    if m:
        started = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    return block, started


def parse_outcome(block: list[str]) -> tuple[int | None, int | None, dict[str, str]]:
    """Pull the DONE tally and the per-job statuses out of a refresh block.

    Returns (ok_count, total_count, {job_name: "OK"|"FAILED"}). The counts are
    None when the block has no DONE line at all, which means the run is still in
    progress or died partway — a distinct condition from "ran and failed".
    """
    ok = total = None
    jobs: dict[str, str] = {}

    for line in block:
        m = re.search(r"DONE: (\d+)/(\d+) jobs succeeded", line)
        if m:
            ok, total = int(m.group(1)), int(m.group(2))
            continue
        m = re.search(r"^\[.*?\]\s{2,}(\w+): (OK|FAILED)$", line)
        if m:
            jobs[m.group(1)] = m.group(2)

    return ok, total, jobs


# --------------------------------------------------------------------------
# Independent checks — each returns (passed, one-line description)
# --------------------------------------------------------------------------

def check_backup(since: datetime | None) -> tuple[bool, str]:
    """A timestamped DB copy newer than the run start proves backup_db.py ran."""
    if not BACKUP_DIR.exists():
        return False, f"backup dir missing: {BACKUP_DIR}"

    backups = sorted(BACKUP_DIR.glob("amip_*.duckdb"),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    if not backups:
        return False, "no backups found"

    newest = backups[0]
    mtime = datetime.fromtimestamp(newest.stat().st_mtime)
    size_gb = newest.stat().st_size / 1e9
    if since and mtime < since:
        return False, f"newest backup {newest.name} predates the run ({mtime:%Y-%m-%d %H:%M})"
    return True, f"{newest.name} at {mtime:%Y-%m-%d %H:%M} ({size_gb:.2f} GB), {len(backups)} retained"


def check_agents() -> tuple[bool, str]:
    """All seven agents still loaded. The watchdog holds no PID between runs."""
    try:
        out = subprocess.run(["launchctl", "list"], capture_output=True,
                             text=True, timeout=30).stdout
    except Exception as e:
        return False, f"launchctl failed: {e}"

    loaded = {line.split()[2] for line in out.splitlines()
              if len(line.split()) >= 3 and line.split()[2].startswith("com.amip.")}
    missing = [a for a in AGENTS if a not in loaded]
    if missing:
        return False, f"NOT loaded: {', '.join(missing)}"
    return True, f"all {len(AGENTS)} loaded"


def check_api() -> tuple[bool, str]:
    """The public path end to end: Cloudflare edge -> tunnel -> Mac."""
    req = urllib.request.Request(HEALTH_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode()[:200]
            return r.status == 200, f"HTTP {r.status} {body}"
    except Exception as e:
        return False, f"unreachable: {e}"


def check_poller_gap(since: datetime | None) -> tuple[bool, str]:
    """No new stall since the refresh restarted the poller.

    Read-only connection. If the poller holds the write lock at this instant the
    read is refused; that is a transient collision and not evidence of a stall,
    so it is reported as a skip rather than a failure.
    """
    try:
        import duckdb
    except ImportError:
        return True, "duckdb unavailable — skipped"

    try:
        con = duckdb.connect(str(SPEED_DB), read_only=True)
    except Exception as e:
        return True, f"DB locked, skipped ({str(e)[:60]})"

    try:
        window = since - timedelta(hours=1) if since else datetime.now() - timedelta(hours=6)
        rows = con.execute(
            "SELECT DISTINCT ts_interval FROM speed_observations "
            "WHERE ts_interval >= ? ORDER BY 1", [window]).fetchall()
        if not rows:
            return False, f"NO intervals since {window:%Y-%m-%d %H:%M} — poller is not collecting"

        stamps = [r[0] for r in rows]
        gaps = [(a, b) for a, b in zip(stamps, stamps[1:])
                if (b - a).total_seconds() / 60 > MAX_GAP_MIN]
        latest_age = (datetime.now() - stamps[-1]).total_seconds() / 60

        if gaps:
            worst = max(gaps, key=lambda g: g[1] - g[0])
            mins = (worst[1] - worst[0]).total_seconds() / 60
            return False, f"{len(gaps)} gap(s) >{MAX_GAP_MIN}min, worst {mins:.0f}min before {worst[1]}"
        return True, f"{len(stamps)} intervals, no gap >{MAX_GAP_MIN}min, latest {stamps[-1]} ({latest_age:.0f}min ago)"
    finally:
        con.close()


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def notify(title: str, message: str) -> None:
    """Fire a macOS notification. Best-effort — never let this sink the report."""
    safe = message.replace('"', "'").replace("\\", "")[:240]
    try:
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{safe}" with title "{title}"'],
            capture_output=True, timeout=15)
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the 4am full refresh")
    parser.add_argument("--no-notify", action="store_true",
                        help="write the report but skip the macOS notification")
    args = parser.parse_args()

    out: list[str] = []
    def say(s: str = "") -> None:
        out.append(s)
        print(s)

    now = datetime.now()
    say("=" * 72)
    say(f"FULL REFRESH CHECK — {now:%Y-%m-%d %H:%M:%S} AEST")
    say("=" * 72)

    block, started = last_full_refresh(REFRESH_LOG)
    if not block:
        say("FAIL: no FULL REFRESH block found in the log at all.")
        verdict, headline = "FAIL", "No full refresh has ever run"
    else:
        ok, total, jobs = parse_outcome(block)
        age_h = (now - started).total_seconds() / 3600 if started else None

        say(f"Run started : {started}" + (f"  ({age_h:.1f}h ago)" if age_h is not None else ""))
        say(f"Tally       : {ok}/{total}" if ok is not None else "Tally       : NO DONE LINE — run incomplete or died partway")
        say("")

        failed = sorted(j for j, s in jobs.items() if s == "FAILED")
        unexpected = [j for j in failed if j not in KNOWN_BAD]
        expected_bad = [j for j in failed if j in KNOWN_BAD]

        if jobs:
            say("Jobs:")
            for job in sorted(jobs):
                mark = "OK  " if jobs[job] == "OK" else ("fail" if job in KNOWN_BAD else "FAIL")
                note = "  (known dead at source, not a regression)" if job in expected_bad else ""
                say(f"  {mark}  {job}{note}")
            say("")

        # Verdict: the run must have finished, and every failure must be one of
        # the two jobs already broken upstream before the migration.
        stale = age_h is not None and age_h > 12
        if ok is None and age_h is not None and age_h < 1.5:
            # No DONE line yet, but the run is young. Today's worst case took a
            # full hour (04:00 -> 05:00:03, every job timing out), so under 90
            # minutes this is very likely still working, not dead.
            verdict, headline = "IN PROGRESS", f"Started {age_h * 60:.0f}min ago, no result yet"
        elif ok is None:
            verdict, headline = "FAIL", "Run did not finish — no DONE line"
        elif stale:
            verdict, headline = "STALE", f"Newest full refresh is {age_h:.0f}h old — it did not fire"
        elif unexpected:
            verdict, headline = "FAIL", f"{ok}/{total}, unexpected failures: {', '.join(unexpected)}"
        else:
            verdict, headline = "PASS", f"{ok}/{total} — only the two known-dead jobs failed"

    say("Independent checks:")
    results = [
        ("backup", check_backup(started)),
        ("agents", check_agents()),
        ("public API", check_api()),
        ("poller continuity", check_poller_gap(started)),
    ]
    for name, (passed, detail) in results:
        say(f"  {'OK  ' if passed else 'FAIL'}  {name}: {detail}")

    if any(not p for _, (p, _) in results) and verdict == "PASS":
        broken = [n for n, (p, _) in results if not p]
        verdict = "FAIL"
        headline = f"Refresh ran, but {', '.join(broken)} failed"

    say("")
    say(f"VERDICT: {verdict} — {headline}")
    say("=" * 72)

    REPORT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_LOG.open("a") as fh:
        fh.write("\n".join(out) + "\n\n")

    if not args.no_notify:
        notify(f"AMIP refresh: {verdict}", headline)

    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
