#!/usr/bin/env python3
"""
generate.py — Render every AMIP LaunchAgent plist from one table.

Seven agents differ only in their program arguments, working directory and
restart policy. One table renders all of them, so a path change is a one-line
edit rather than seven — which is how the old bluetooth-archive agent silently
kept pointing at a pre-move path.

Restart policy comes in two shapes:
  * Long-running services use KeepAlive with a PathState guard. Measured
    behaviour: the guard is a START and RESTART-SUPPRESSION condition, NOT a
    stop condition. While the guard path is missing launchd will not start or
    restart the job, so an unmounted T9 volume does not produce a crash loop
    against a missing database; when the drive reappears launchd starts the job
    again with no intervention. A process that is ALREADY RUNNING when the
    volume goes away keeps running — deleting the guard file does not signal it
    (verified still alive at +30s). RunAtLoad also starts the job regardless of
    the guard's state at load time.
  * The watchdog is oneshot, on a 15-minute StartInterval.

Run: python3 deploy/launchd/generate.py
"""

import plistlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent                      # /Volumes/T9/Projects/Traffic Movement
FILEVAULT = REPO.parent / "filevault"          # /Volumes/T9/Projects/filevault

# Logs CANNOT live beside the code on T9. Measured: launchd resolves
# StandardOutPath/StandardErrorPath before the program runs, and if that path
# is on the external T9 volume the job fails to start at all — exit 78
# (EX_CONFIG), no PID assigned, no log written anywhere to explain why.
# Confirmed by isolation: taking the real com.amip.bluetooth plist and
# changing only its two log paths from T9 to /tmp made it start immediately.
# ~/Library/Logs is the conventional macOS location for user-level app logs,
# it lives on the internal, FileVault-protected disk, and launchd can write
# to it. Do not move this back to the repo — it will silently break every
# agent's startup again.
LOGS = Path.home() / "Library" / "Logs" / "amip"

PY = str(REPO / "venv" / "bin" / "python3")
UVICORN = str(REPO / "venv" / "bin" / "uvicorn")
GUNICORN = str(FILEVAULT / "venv" / "bin" / "gunicorn")
CLOUDFLARED = "/opt/homebrew/bin/cloudflared"

# Existence of the main database proves both that T9 is mounted and that the
# repo is intact. filevault guards on its own tree for the same reason.
GUARD_REPO = str(REPO / "db" / "amip.duckdb")
GUARD_FILEVAULT = str(FILEVAULT / "app.py")

AGENTS = [
    {
        "label": "com.amip.api",
        "args": [UVICORN, "api.main:app", "--host", "127.0.0.1", "--port", "8000"],
        "cwd": str(REPO),
        "guard": GUARD_REPO,
    },
    {
        "label": "com.amip.bluetooth",
        "args": [PY, "scripts/poll_bluetooth.py", "--loop"],
        "cwd": str(REPO),
        "guard": GUARD_REPO,
    },
    {
        "label": "com.amip.refresh",
        "args": [PY, "scripts/daily_refresh.py", "--loop"],
        "cwd": str(REPO),
        "guard": GUARD_REPO,
    },
    {
        "label": "com.amip.bluetooth-archive",
        "args": [PY, "archive-poller/bluetooth_archive.py", "--loop"],
        # cwd is the repo root like every other repo-based agent, NOT the
        # archive-poller subdirectory — the arg already carries that prefix, and
        # pairing both would resolve to archive-poller/archive-poller/. The script
        # derives its DB, log and .env paths from __file__, so cwd is behaviourally
        # irrelevant; uniformity here is what prevents that class of mismatch.
        "cwd": str(REPO),
        "guard": GUARD_REPO,
    },
    {
        "label": "com.amip.filevault",
        "args": [GUNICORN, "-w", "4", "-b", "127.0.0.1:5050", "app:app"],
        "cwd": str(FILEVAULT),
        "guard": GUARD_FILEVAULT,
    },
    {
        "label": "com.amip.tunnel",
        "args": [CLOUDFLARED, "tunnel", "run", "melbtraffic"],
        "cwd": str(REPO),
        "guard": GUARD_REPO,
    },
    {
        "label": "com.amip.watchdog",
        "args": [PY, "scripts/watchdog.py", "--verbose"],
        "cwd": str(REPO),
        "interval": 900,
    },
]


def build(agent):
    """Turn one table row into a launchd plist dictionary."""
    log_path = str(LOGS / f"{agent['label']}.log")
    plist = {
        "Label": agent["label"],
        "ProgramArguments": agent["args"],
        "WorkingDirectory": agent["cwd"],
        "RunAtLoad": True,
        "StandardOutPath": log_path,
        "StandardErrorPath": log_path,
        "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
    }
    if "interval" in agent:
        plist["StartInterval"] = agent["interval"]
    else:
        plist["KeepAlive"] = {"PathState": {agent["guard"]: True}}
        plist["ThrottleInterval"] = 10
    return plist


def main():
    LOGS.mkdir(exist_ok=True)
    for agent in AGENTS:
        out = HERE / f"{agent['label']}.plist"
        with out.open("wb") as fh:
            plistlib.dump(build(agent), fh)
        print(f"  wrote {out.name}")
    print(f"\n{len(AGENTS)} plists generated in {HERE}")


if __name__ == "__main__":
    main()
