#!/usr/bin/env python3
"""
generate.py — Render every AMIP LaunchAgent plist from one table.

Seven agents differ only in their program arguments, working directory and
restart policy. One table renders all of them, so a path change is a one-line
edit rather than seven — which is how the old bluetooth-archive agent silently
kept pointing at a pre-move path.

Restart policy comes in two shapes:
  * Long-running services use KeepAlive with a PathState guard. launchd runs
    them only while the guard path exists, so an unmounted T9 volume stops the
    stack cleanly instead of thrashing against a missing database, and mounting
    the drive starts everything again with no intervention.
  * The watchdog is oneshot, on a 15-minute StartInterval.

Run: python3 deploy/launchd/generate.py
"""

import plistlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent                      # /Volumes/T9/Projects/Traffic Movement
FILEVAULT = REPO.parent / "filevault"          # /Volumes/T9/Projects/filevault
LOGS = REPO / "logs"

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
        "cwd": str(REPO / "archive-poller"),
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
