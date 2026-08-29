# VPS → Mac Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire the Contabo VPS by moving the melbtraffic API, its three pollers and the filevault document server onto the always-on Mac, fronted by a Cloudflare Tunnel, with no data loss and a Bluetooth-polling gap measured in minutes.

**Architecture:** The Mac runs seven LaunchAgents (API, three pollers, filevault, tunnel, watchdog) against DuckDB files on the T9 external volume. `cloudflared` holds an outbound tunnel to Cloudflare's edge, which routes `api.melbtraffic.com` → `:8000` and `files.melbtraffic.com` → `:5050`. Caddy, DuckDNS and the VPS are retired. Tasks 1–8 are non-destructive and leave the live site untouched; Task 9 is the first change visible to production.

**Tech Stack:** Python 3.14.4 + venv, DuckDB, FastAPI/uvicorn, Flask/gunicorn, launchd, cloudflared, Cloudflare Pages, rsync over SSH.

**Spec:** `docs/superpowers/specs/2026-08-29-vps-to-mac-migration-design.md`

## Global Constraints

- Project root: `/Volumes/T9/Projects/Traffic Movement` — every path resolves from it; nothing hardcodes `/opt/amip`
- filevault destination: `/Volumes/T9/Projects/filevault` (D9), its own directory outside the traffic repo
- Tunnel name: `melbtraffic` (D10) — one named tunnel serves both hostnames
- Public hostnames: `api.melbtraffic.com` → `127.0.0.1:8000`, `files.melbtraffic.com` → `127.0.0.1:5050`
- `CORS_ORIGINS=https://melbtraffic.com,https://www.melbtraffic.com,https://traffic-movement.pages.dev`
- LaunchAgent labels: `com.amip.api`, `com.amip.bluetooth`, `com.amip.refresh`, `com.amip.bluetooth-archive`, `com.amip.filevault`, `com.amip.tunnel`, `com.amip.watchdog`
- Volume guard path: `/Volumes/T9/Projects/Traffic Movement/db/amip.duckdb`
- Plists are version-controlled in `deploy/launchd/` and symlinked into `~/Library/LaunchAgents` (D7)
- Test convention: standalone scripts with PASS/FAIL counters run via `python3`, matching `scripts/test_summaries.py`. No pytest.
- **Tasks 1–8 must not modify the VPS in any way.** The live site stays up throughout. Task 9 is the first production-affecting step and requires explicit go-ahead.

---

### Task 1: Platform service-control layer

The watchdog shells out to `systemctl` (`scripts/watchdog.py:95,109,113`), which does not exist on macOS. Extract that knowledge into one module so the watchdog stops caring which init system it is on. This is the only task with real unit tests — its failure mode is silent (a watchdog that wrongly believes services are healthy, or that cannot restart them, is worse than no watchdog).

**Files:**
- Create: `scripts/service_control.py`
- Create: `scripts/test_service_control.py`
- Modify: `scripts/watchdog.py:40-44` (constants), `scripts/watchdog.py:91-121` (`check_services`)

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces: `service_control.get_controller(platform=None)` returning an object with `is_active(service_id) -> bool`, `start(service_id) -> bool` and attribute `platform_key -> str`; `service_control.service_ids(controller) -> list[str]`; module constant `SERVICE_IDS: dict[str, dict[str, str]]`

- [ ] **Step 1: Write the failing test**

Create `scripts/test_service_control.py`:

```python
"""
test_service_control.py — Unit tests for the platform service-control layer.

Replaces subprocess.run with a fake so the tests never touch real systemd or
launchd. Verifies both controllers issue the right commands and read their
output correctly.

Run: python3 scripts/test_service_control.py
"""

import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import service_control

PASS = 0
FAIL = 0


def check(label, actual, expected):
    """Compare one value and record the result."""
    global PASS, FAIL
    if actual == expected:
        print(f"  OK   {label}")
        PASS += 1
    else:
        print(f"  FAIL {label}: got {actual!r}, expected {expected!r}")
        FAIL += 1


class FakeRun:
    """Stands in for subprocess.run. Records calls, returns canned results."""

    def __init__(self, stdout="", returncode=0):
        self.stdout = stdout
        self.returncode = returncode
        self.calls = []

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        return subprocess.CompletedProcess(
            args=cmd, returncode=self.returncode, stdout=self.stdout, stderr=""
        )


def with_fake_run(fake, fn):
    """Run fn with subprocess.run patched, always restoring the original."""
    original = service_control.subprocess.run
    service_control.subprocess.run = fake
    try:
        return fn()
    finally:
        service_control.subprocess.run = original


def test_systemd_is_active():
    c = service_control.SystemdController()

    fake = FakeRun(stdout="active\n")
    check("systemd active -> True", with_fake_run(fake, lambda: c.is_active("amip-api")), True)
    check("systemd is-active command", fake.calls[0], ["systemctl", "is-active", "amip-api"])

    fake = FakeRun(stdout="inactive\n")
    check("systemd inactive -> False", with_fake_run(fake, lambda: c.is_active("amip-api")), False)

    fake = FakeRun(stdout="failed\n")
    check("systemd failed -> False", with_fake_run(fake, lambda: c.is_active("amip-api")), False)


def test_systemd_start():
    c = service_control.SystemdController()
    fake = FakeRun()
    with_fake_run(fake, lambda: c.start("amip-refresh"))
    check("systemd start command", fake.calls[0],
          ["sudo", "-n", "systemctl", "start", "amip-refresh"])


def test_launchd_is_active():
    c = service_control.LaunchdController()

    # A running job prints a plist fragment containing a PID key.
    fake = FakeRun(stdout='{\n\t"PID" = 4242;\n\t"Label" = "com.amip.api";\n}\n')
    check("launchd running -> True", with_fake_run(fake, lambda: c.is_active("com.amip.api")), True)
    check("launchd list command", fake.calls[0], ["launchctl", "list", "com.amip.api"])

    # Loaded but stopped: exit 0, no PID key.
    fake = FakeRun(stdout='{\n\t"Label" = "com.amip.api";\n}\n')
    check("launchd loaded-not-running -> False",
          with_fake_run(fake, lambda: c.is_active("com.amip.api")), False)

    # Not loaded at all: non-zero exit.
    fake = FakeRun(stdout="", returncode=113)
    check("launchd not-loaded -> False",
          with_fake_run(fake, lambda: c.is_active("com.amip.api")), False)


def test_launchd_start():
    c = service_control.LaunchdController()
    fake = FakeRun()
    with_fake_run(fake, lambda: c.start("com.amip.bluetooth"))
    cmd = fake.calls[0]
    check("launchd kickstart verb", cmd[:2], ["launchctl", "kickstart"])
    check("launchd kickstart target shape", cmd[2].startswith("gui/"), True)
    check("launchd kickstart target label", cmd[2].endswith("/com.amip.bluetooth"), True)


def test_controller_selection():
    check("darwin -> launchd",
          service_control.get_controller("darwin").platform_key, "launchd")
    check("linux -> systemd",
          service_control.get_controller("linux").platform_key, "systemd")


def test_service_ids_per_platform():
    check("launchd ids",
          service_control.service_ids(service_control.get_controller("darwin")),
          ["com.amip.api", "com.amip.bluetooth", "com.amip.refresh"])
    check("systemd ids",
          service_control.service_ids(service_control.get_controller("linux")),
          ["amip-api", "amip-bluetooth", "amip-refresh"])


def main():
    print("Service control layer tests\n")
    for fn in (test_systemd_is_active, test_systemd_start,
               test_launchd_is_active, test_launchd_start,
               test_controller_selection, test_service_ids_per_platform):
        print(f"{fn.__name__}:")
        fn()
    print(f"\n  {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd "/Volumes/T9/Projects/Traffic Movement"
python3 scripts/test_service_control.py
```

Expected: `ModuleNotFoundError: No module named 'service_control'`

- [ ] **Step 3: Write the implementation**

Create `scripts/service_control.py`:

```python
"""
service_control.py — Platform-agnostic service supervision

The watchdog asks two questions of the host's init system: "is this service
running?" and "start it". systemd answers them on the Linux VPS, launchd on
the Mac. This module is the only place in the codebase that knows which.

Adding a service means adding one row to SERVICE_IDS — the logical name the
watchdog uses, mapped to the identifier each platform expects.

Consumed by: scripts/watchdog.py
"""

import os
import subprocess
import sys

# Logical name -> platform-specific service identifier.
SERVICE_IDS = {
    "api":       {"systemd": "amip-api",       "launchd": "com.amip.api"},
    "bluetooth": {"systemd": "amip-bluetooth", "launchd": "com.amip.bluetooth"},
    "refresh":   {"systemd": "amip-refresh",   "launchd": "com.amip.refresh"},
}

# The order the watchdog reports services in.
SERVICE_ORDER = ("api", "bluetooth", "refresh")


class SystemdController:
    """Service control via systemctl. Used on the Linux VPS."""

    platform_key = "systemd"

    def is_active(self, service_id):
        """True when systemctl reports the unit as active."""
        r = subprocess.run(["systemctl", "is-active", service_id],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() == "active"

    def start(self, service_id):
        """Start the unit. Requires passwordless sudo, as configured on the VPS."""
        subprocess.run(["sudo", "-n", "systemctl", "start", service_id],
                       capture_output=True, timeout=10)
        return True


class LaunchdController:
    """Service control via launchctl. Used on macOS.

    `launchctl list <label>` exits non-zero when the job is not loaded at all,
    and prints a plist fragment containing a `"PID" = <n>;` line only while the
    job is actually running — a loaded-but-stopped job has no PID key. Both
    cases mean "not active" to the watchdog.
    """

    platform_key = "launchd"

    def is_active(self, service_id):
        """True when launchctl reports a live PID for the label."""
        r = subprocess.run(["launchctl", "list", service_id],
                           capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return False
        return '"PID" =' in r.stdout

    def start(self, service_id):
        """Kickstart the agent in the current user's GUI domain."""
        target = f"gui/{os.getuid()}/{service_id}"
        subprocess.run(["launchctl", "kickstart", target],
                       capture_output=True, timeout=10)
        return True


def get_controller(platform=None):
    """Return the controller for this platform.

    `platform` is overridable so tests can exercise both branches on one host.
    """
    plat = platform if platform is not None else sys.platform
    return LaunchdController() if plat == "darwin" else SystemdController()


def service_ids(controller):
    """The platform-specific identifiers, in the watchdog's reporting order."""
    return [SERVICE_IDS[name][controller.platform_key] for name in SERVICE_ORDER]
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python3 scripts/test_service_control.py
```

Expected: `16 passed, 0 failed`, exit code 0

- [ ] **Step 5: Rewrite `check_services` to use the layer**

In `scripts/watchdog.py`, replace lines 91–121 (the whole `check_services` function) with:

```python
def check_services(result, auto_restart=True):
    """Check every AMIP service is running. Restart any that are not.

    Service supervision is delegated to scripts/service_control.py so this
    function reads the same on the VPS (systemd) and the Mac (launchd).
    """
    controller = service_control.get_controller()
    for svc in service_control.service_ids(controller):
        try:
            active = controller.is_active(svc)
        except Exception as e:
            result.fail(f"service/{svc}", f"check failed: {e}")
            continue

        if active:
            result.ok(f"service/{svc}", "active")
            continue

        result.fail(f"service/{svc}", "not running")
        if not auto_restart:
            continue

        log(f"  Restarting {svc}...")
        try:
            controller.start(svc)
            time.sleep(3)  # give the supervisor a moment to report the new state
            if controller.is_active(svc):
                log(f"  {svc} restarted successfully")
            else:
                log(f"  {svc} FAILED to restart")
        except Exception as e:
            log(f"  {svc} restart error: {e}")
```

- [ ] **Step 6: Update the watchdog's imports and constants**

In `scripts/watchdog.py`, add to the import block (after `import subprocess`):

```python
import time
```

and after the `duckdb` import add:

```python
import service_control
```

Then replace lines 40–44 with:

```python
API_BASE = "https://api.melbtraffic.com"
FRONTEND_URL = "https://melbtraffic.com"

# Service identifiers now live in scripts/service_control.py (SERVICE_IDS),
# which maps them per platform. Nothing here needs to know the names.
```

Delete the now-unused `SERVICES` list and the local `import time` inside the old restart block if one remains.

- [ ] **Step 7: Verify the watchdog still runs end to end**

```bash
python3 scripts/watchdog.py --check-only --verbose
```

Expected: it runs to completion and reports on `com.amip.*` services (all failing — the agents do not exist yet, which is correct at this point). It must not raise `NameError`, `ImportError`, or `FileNotFoundError: systemctl`.

- [ ] **Step 8: Commit**

```bash
git add scripts/service_control.py scripts/test_service_control.py scripts/watchdog.py
git commit -m "feat: platform-agnostic service control for watchdog

Extracts systemd/launchd differences into scripts/service_control.py so the
watchdog runs unchanged on both the VPS and the Mac. Points API_BASE and
FRONTEND_URL at the melbtraffic.com hostnames."
```

---

### Task 2: LaunchAgent definitions

Seven agents share one shape and differ in a handful of fields. Hand-maintained XML is precisely how `com.amip.bluetooth-archive` kept a stale `/Users/doug/Projects` path unnoticed after the project moved to T9 — so the plists are rendered from a single table instead, and paths cannot drift per-file.

**Files:**
- Create: `deploy/launchd/generate.py`
- Create: `deploy/launchd/install.sh`
- Create (generated): `deploy/launchd/com.amip.{api,bluetooth,refresh,bluetooth-archive,filevault,tunnel,watchdog}.plist`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces: seven plists on disk; `install.sh` symlinks them into `~/Library/LaunchAgents` and loads them

- [ ] **Step 1: Write the generator**

Create `deploy/launchd/generate.py`:

```python
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
```

- [ ] **Step 2: Generate the plists and validate them**

```bash
cd "/Volumes/T9/Projects/Traffic Movement"
python3 deploy/launchd/generate.py
for f in deploy/launchd/*.plist; do plutil -lint "$f"; done
```

Expected: seven `wrote …` lines, then `OK` from `plutil` for each of the seven files.

- [ ] **Step 3: Verify the generated content is what launchd needs**

```bash
plutil -p deploy/launchd/com.amip.api.plist
plutil -p deploy/launchd/com.amip.watchdog.plist
```

Expected: the API plist shows `KeepAlive => {"PathState" => {"/Volumes/T9/.../db/amip.duckdb" => 1}}` and no `StartInterval`; the watchdog plist shows `StartInterval => 900` and no `KeepAlive`. Every path is absolute and under `/Volumes/T9`.

- [ ] **Step 4: Write the installer**

Create `deploy/launchd/install.sh`:

```bash
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
```

- [ ] **Step 5: Verify the installer links without loading**

```bash
bash deploy/launchd/install.sh
ls -l ~/Library/LaunchAgents/com.amip.*.plist
```

Expected: seven symlinks pointing into `/Volumes/T9/Projects/Traffic Movement/deploy/launchd/`. Do **not** pass `--load` yet — the venvs, the tunnel and the data are not in place until Tasks 3–8.

- [ ] **Step 6: Commit**

```bash
git add deploy/launchd/
git commit -m "feat: launchd agent definitions generated from one table

Seven agents rendered from a single table in generate.py, so paths cannot
drift per-file. Long-running agents use KeepAlive PathState guards so an
unmounted T9 volume stops them cleanly and remounting restarts them."
```

---

### Task 3: Python environments

The VPS uses a venv; the Mac has been running `pip3 --break-system-packages`. Match the VPS so the plists' absolute interpreter paths are real.

**Files:**
- Create: `venv/` (gitignored)
- Modify: `.gitignore` if `venv/` is not already covered

**Interfaces:**
- Consumes: nothing
- Produces: `venv/bin/python3` and `venv/bin/uvicorn`, the interpreter paths Task 2's plists reference

- [ ] **Step 1: Create the venv and install dependencies**

```bash
cd "/Volumes/T9/Projects/Traffic Movement"
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
```

- [ ] **Step 2: Verify every import the services need resolves**

```bash
./venv/bin/python3 -c "import duckdb, fastapi, uvicorn, requests, pyproj, openpyxl; print('all imports OK')"
./venv/bin/uvicorn --version
```

Expected: `all imports OK`, then a uvicorn version string.

- [ ] **Step 3: Confirm the paths the plists expect exist**

```bash
test -x venv/bin/python3 && test -x venv/bin/uvicorn && echo "interpreter paths OK"
```

Expected: `interpreter paths OK`

- [ ] **Step 4: Ensure the venv is gitignored**

```bash
grep -q '^venv/' .gitignore || echo 'venv/' >> .gitignore
grep -n 'venv' .gitignore
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore
git commit -m "chore: ignore project venv"
```

---

### Task 4: Environment file reconciliation

The local `.env` has three keys; the VPS has five. `CORS_ORIGINS` is the one that matters — without it the Mac's API serves curl happily and rejects every request from the real frontend, which is a confusing way to discover a problem at cutover.

**Files:**
- Modify: `/Volumes/T9/Projects/Traffic Movement/.env` (gitignored — never committed)
- Modify: `api/main.py` (add the `.env` loader — see Step 5)

**Interfaces:**
- Consumes: nothing
- Produces: a `.env` with all five keys, and an API process that actually reads it

**Ruling R1 (pre-flight scan, recorded in the SDD ledger):** on the VPS, systemd
injected `.env` into every service via `EnvironmentFile=`. launchd has no equivalent
directive, and `api/main.py:88` only does `os.environ.get("CORS_ORIGINS", _default_origins)`
where the default is localhost-only. Putting `CORS_ORIGINS` in `.env` therefore fixes
nothing on its own — the API would silently reject every request from melbtraffic.com.
The pollers are unaffected: `poll_bluetooth.py` and `poll_fuel_prices.py` already load
`.env` themselves. Step 5 makes the API do the same. Putting the values in the plists'
`EnvironmentVariables` was rejected: `deploy/launchd/` is version-controlled, and that
would commit secrets to git.

- [ ] **Step 1: Compare local and VPS keys**

```bash
cd "/Volumes/T9/Projects/Traffic Movement"
echo "--- local ---"; cut -d= -f1 .env | grep -v '^#' | grep -v '^$'
echo "--- vps ---";   ssh amip "cut -d= -f1 /opt/amip/.env | grep -v '^#' | grep -v '^\$'"
```

Expected: local shows `VIC_BLUETOOTH_API_KEY`, `SERVO_SAVER_CONSUMER_ID`, `EIA_API_KEY`; the VPS additionally shows `CORS_ORIGINS` and `AMIP_DEBUG`.

- [ ] **Step 2: Append the two missing keys**

```bash
cat >> .env << 'EOF'
CORS_ORIGINS=https://melbtraffic.com,https://www.melbtraffic.com,https://traffic-movement.pages.dev
AMIP_DEBUG=false
EOF
```

- [ ] **Step 3: Verify the three secret values match the VPS**

Compare without printing secrets to the terminal:

```bash
for k in VIC_BLUETOOTH_API_KEY SERVO_SAVER_CONSUMER_ID EIA_API_KEY; do
  local_hash=$(grep "^$k=" .env | cut -d= -f2- | shasum | cut -c1-8)
  vps_hash=$(ssh amip "grep '^$k=' /opt/amip/.env | cut -d= -f2- | shasum | cut -c1-8")
  [ "$local_hash" = "$vps_hash" ] && echo "  OK   $k" || echo "  DIFF $k — local key differs from VPS"
done
```

Expected: `OK` for all three. Any `DIFF` must be resolved by copying the VPS value across before proceeding — a stale local API key means a poller that starts and then silently fails to fetch.

- [ ] **Step 4: Confirm `.env` is not tracked**

```bash
git check-ignore -v .env && echo "gitignored, correct"
```

Expected: a line showing the matching `.gitignore` rule. If this prints nothing, `.env` is tracked and must be removed from the index before any further commit.

- [ ] **Step 5: Make the API load `.env` itself**

`api/main.py` already imports `os` and `Path`. Add this immediately after the existing
import block (after the `from api import cache` line), mirroring the loader already used
in `scripts/poll_bluetooth.py:39-50` — `api/main.py` sits one level below the repo root,
exactly like the scripts, so the same path expression is correct:

```python
# Environment — systemd injected .env via EnvironmentFile= on the VPS; launchd has no
# equivalent, so the API loads .env itself. Same pattern as scripts/poll_bluetooth.py.
try:
    from dotenv import load_dotenv
except ImportError:
    # If python-dotenv not installed, read .env manually
    def load_dotenv():
        env_path = Path(__file__).resolve().parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

load_dotenv()
```

`load_dotenv()` must be called BEFORE the `_origins` line at `api/main.py:88`, since that
line reads `os.environ` at import time. `os.environ.setdefault` means a variable already
set in the real environment always wins over the file.

- [ ] **Step 6: Verify the API picks up CORS_ORIGINS from the file**

```bash
cd "/Volumes/T9/Projects/Traffic Movement"
python3 -c "
import sys; sys.path.insert(0, '.')
from api.main import _origins
print('origins:', _origins)
assert 'https://melbtraffic.com' in _origins, 'CORS_ORIGINS did not reach the app'
print('OK — .env reached the FastAPI app')
"
```

Expected: the three production origins printed, then `OK`. This is the check that would
have caught the defect at cutover instead of during it.

- [ ] **Step 7: Commit the code change**

```bash
git add api/main.py
git commit -m "fix: load .env in the API process

launchd has no EnvironmentFile equivalent, so the API must read .env itself
or CORS_ORIGINS never reaches it and the production frontend is rejected."
```

`.env` itself is deliberately untracked and is never committed.

---

### Task 5: macOS host prerequisites

Measured state: `sleep`, `standby` and `disksleep` are already `0`, so the poller is not at risk of sleep gaps. Two things remain, and one of them may turn out to be a blocker.

**Files:** none — host configuration only

**Interfaces:**
- Consumes: nothing
- Produces: a host that recovers unattended from a power cut, or a documented reason it cannot

- [ ] **Step 1: Record the current power settings**

```bash
pmset -g custom | grep -Ei "^ +(sleep|standby|autopoweroff|autorestart|disksleep|womp)"
```

Expected: `sleep 0`, `standby 0`, `disksleep 0`, `autorestart 0`. Note `autopoweroff` is absent on this machine — including it in a `pmset` command makes `pmset` reject the whole invocation, so it must be omitted.

- [ ] **Step 2: Enable restart after power failure**

```bash
sudo pmset -a autorestart 1
pmset -g custom | grep -i autorestart
```

Expected: `autorestart 1`

- [ ] **Step 3: Check whether the boot volume is encrypted**

```bash
fdesetup status
```

This determines whether unattended recovery is achievable at all. If it reports **`FileVault is On`**, macOS demands the unlock password at startup and automatic login cannot proceed until a human types it — no launchd configuration changes that. Record the result and tell the user before continuing: with FileVault on, a power cut means downtime until someone unlocks the Mac, and the plan's reboot test (Task 12) will fail by design rather than by fault.

- [ ] **Step 4: Enable automatic login**

Verified off at planning time (`com.apple.loginwindow autoLoginUser` unset). This is a GUI setting and cannot be scripted reliably on modern macOS:

**User action:** System Settings → Users & Groups → "Automatically log in as" → select the `doug` account.

Then confirm:

```bash
defaults read /Library/Preferences/com.apple.loginwindow autoLoginUser
```

Expected: `doug`

- [ ] **Step 5: Record the outcome in the spec**

Append the measured `fdesetup status` result to the spec's §5 so the decision is captured with its evidence:

```bash
cd "/Volumes/T9/Projects/Traffic Movement"
# Edit docs/superpowers/specs/2026-08-29-vps-to-mac-migration-design.md §5,
# replacing "must be checked during pre-stage" with the actual result.
git add docs/superpowers/specs/2026-08-29-vps-to-mac-migration-design.md
git commit -m "docs: record boot volume encryption state for migration"
```

---

### Task 6: Cloudflare Tunnel

Create and authenticate the tunnel without publishing any DNS. Nothing here is visible to production — the tunnel simply has no routes yet.

**Files:**
- Create: `~/.cloudflared/<tunnel-uuid>.json` (credentials, never committed)
- Create: `~/.cloudflared/config.yml`

**Interfaces:**
- Consumes: nothing
- Produces: a named tunnel `melbtraffic` with a UUID, and an ingress config mapping both hostnames to local ports. Task 11 publishes the DNS routes.

- [ ] **Step 1: Install cloudflared**

```bash
brew install cloudflared
cloudflared --version
```

Expected: a version string. Homebrew 6.0.11 is present at `/opt/homebrew/bin/brew` and the `cloudflared` formula is available.

- [ ] **Step 2: Authenticate against the Cloudflare account**

```bash
cloudflared tunnel login
```

Opens a browser. **User action:** select the `melbtraffic.com` zone and authorise. This writes `~/.cloudflared/cert.pem`.

- [ ] **Step 3: Create the named tunnel**

```bash
cloudflared tunnel create melbtraffic
cloudflared tunnel list
```

Expected: a UUID and a credentials file path. Record the UUID — it is the CNAME target and the config's `tunnel:` value.

- [ ] **Step 4: Write the ingress config**

Create `~/.cloudflared/config.yml`, substituting the real UUID:

```yaml
# AMIP tunnel — routes two public hostnames to local services on the Mac.
# api.melbtraffic.com   -> FastAPI  (com.amip.api)
# files.melbtraffic.com -> filevault (com.amip.filevault)
tunnel: <TUNNEL-UUID>
credentials-file: /Users/doug/.cloudflared/<TUNNEL-UUID>.json

ingress:
  - hostname: api.melbtraffic.com
    service: http://127.0.0.1:8000
  - hostname: files.melbtraffic.com
    service: http://127.0.0.1:5050
  # Required catch-all: anything else gets a 404 rather than reaching a service.
  - service: http_status:404
```

- [ ] **Step 5: Validate the config**

```bash
cloudflared tunnel ingress validate
```

Expected: `Validating rules from /Users/doug/.cloudflared/config.yml` then `OK`.

- [ ] **Step 6: Verify the ingress rules match the intended hostnames**

```bash
cloudflared tunnel ingress rule https://api.melbtraffic.com/api/health
cloudflared tunnel ingress rule https://files.melbtraffic.com/
```

Expected: the first matches rule 0 → `http://127.0.0.1:8000`; the second matches rule 1 → `http://127.0.0.1:5050`.

- [ ] **Step 7: Back up the tunnel credentials**

The credentials JSON cannot be re-downloaded — losing it means deleting and recreating the tunnel, which changes the UUID and every DNS record.

```bash
cp ~/.cloudflared/*.json ~/.cloudflared/cert.pem "/Volumes/T9/Projects/Traffic Movement/db/backups/cloudflared-credentials-backup/"
```

Create the directory first if needed. Confirm `db/backups/` is gitignored before copying — these are secrets.

---

### Task 7: Bulk data transfer

The long pole, roughly 46.5 GB. The VPS keeps serving throughout; this is a read-only copy.

**Files:**
- Modify: `db/` on the Mac (receives the VPS data)

**Interfaces:**
- Consumes: nothing
- Produces: `db/amip.duckdb`, `db/speed.duckdb`, `db/archive/`, `db/backups/` matching the VPS

- [ ] **Step 1: Move the stale local database aside**

The local `db/amip.duckdb` is 269 MB dated March. Letting rsync write over it in place risks a half-updated file if the transfer is interrupted, and keeping it named the same invites confusion about which is real.

```bash
cd "/Volumes/T9/Projects/Traffic Movement"
mv db/amip.duckdb db/amip.duckdb.stale-2026-03
ls -la db/*.stale-*
```

Also note the orphaned `db/amip_fresh.duckdb.wal` (1.7 MB) — a write-ahead log with no matching database. Leave it for now; it is inspected in Task 14.

- [ ] **Step 2: Confirm free space before starting**

```bash
df -h /Volumes/T9 | tail -1
ssh amip "du -sh /opt/amip/db"
```

Expected: T9 free space comfortably exceeds the VPS `db/` total (~46.5 GB against ~309 GB free).

- [ ] **Step 3: Transfer, resumable and verifiable**

```bash
cd "/Volumes/T9/Projects/Traffic Movement"
rsync -avh --partial --progress --stats \
  amip:/opt/amip/db/ db/
```

`--partial` lets an interrupted transfer resume rather than restart. This takes a long time; run it in a window you can leave.

- [ ] **Step 4: Verify sizes match the source**

```bash
echo "--- vps ---"; ssh amip "du -sh /opt/amip/db/amip.duckdb /opt/amip/db/speed.duckdb /opt/amip/db/archive /opt/amip/db/backups"
echo "--- mac ---"; du -sh db/amip.duckdb db/speed.duckdb db/archive db/backups
```

Expected: matching sizes — approximately 4.1 GB, 2.4 GB, 11 GB, 29 GB.

- [ ] **Step 5: Verify the databases actually open and carry the expected data**

```bash
./venv/bin/python3 -c "
import duckdb
con = duckdb.connect('db/amip.duckdb', read_only=True)
print('daily_station_summary:', con.execute('SELECT count(*) FROM daily_station_summary').fetchone()[0])
print('stations:', con.execute('SELECT count(*) FROM stations').fetchone()[0])
print('latest day:', con.execute('SELECT max(day) FROM daily_station_summary').fetchone()[0])
con.close()
con = duckdb.connect('db/speed.duckdb', read_only=True)
print('speed_observations:', con.execute('SELECT count(*) FROM speed_observations').fetchone()[0])
print('latest speed obs:', con.execute('SELECT max(ts_interval) FROM speed_observations').fetchone()[0])
con.close()
"
```

Expected (measured against the transferred file on 2026-08-29): `daily_station_summary`
842,896 rows, `stations` 3,964, plus a non-zero speed count and a latest speed observation
within minutes of now (the VPS poller is still running at this point).

Note the table names: the live schema has no `hourly_counts` table — the raw hourly data is
served through `daily_station_summary` and `hourly_city_summary`, and the date column on
`daily_station_summary` is `day`, not `date`. The `/api/health` endpoint queries
`daily_station_summary` and `stations`, so the Task 9/10 health-parity checks are unaffected.

---

### Task 8: filevault migration

The real payload is about 56 KB: the app, its templates, its requirements and two uploaded documents. The 23 MB figure is almost entirely a venv that gets rebuilt.

**Files:**
- Create: `/Volumes/T9/Projects/filevault/{app.py,requirements.txt,templates/,uploads/,venv/}`

**Interfaces:**
- Consumes: nothing
- Produces: `/Volumes/T9/Projects/filevault/venv/bin/gunicorn` and `app.py`, the paths Task 2's `com.amip.filevault` plist references

- [ ] **Step 1: Copy the application and its documents**

```bash
mkdir -p /Volumes/T9/Projects/filevault
rsync -avh --exclude venv --exclude __pycache__ \
  amip:/opt/filevault/ /Volumes/T9/Projects/filevault/
ls -la /Volumes/T9/Projects/filevault/ /Volumes/T9/Projects/filevault/uploads/
```

Expected: `app.py`, `requirements.txt`, `templates/`, and `uploads/` containing exactly two files — `Stakeholder-Engagement-First-Meeting-Notes.docx` and `.md`.

- [ ] **Step 2: Verify the documents transferred intact**

```bash
echo "--- vps ---"; ssh amip "sudo shasum /opt/filevault/uploads/*"
echo "--- mac ---"; shasum /Volumes/T9/Projects/filevault/uploads/*
```

Expected: matching checksums. These two files are the only irreplaceable filevault data on the VPS.

- [ ] **Step 3: Build the filevault venv**

```bash
cd /Volumes/T9/Projects/filevault
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt gunicorn
test -x venv/bin/gunicorn && echo "gunicorn path OK"
```

Expected: `gunicorn path OK`. `requirements.txt` is 46 bytes (Flask and Werkzeug); gunicorn is installed explicitly because the VPS unit invokes it and it may not be listed.

- [ ] **Step 4: Smoke-test the app before wiring it to launchd**

```bash
cd /Volumes/T9/Projects/filevault
./venv/bin/gunicorn -w 1 -b 127.0.0.1:5051 app:app &
sleep 3
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5051/
kill %1
```

Expected: `302` (redirect to the login page) or `200`. Anything in the 500 range means the app did not start — check the terminal output before proceeding.

- [ ] **Step 5: DECISION POINT — filevault credentials**

`app.py` hardcodes the Flask `secret_key` (line 34) and an `admin` password (line 53) as literals in source. The app is about to be republished at a new public hostname, which makes this the natural moment to deal with it.

**Recommended: move both to `.env` and rotate them.** The existing password has sat in plaintext in a file that has been read during this migration; rotating costs nothing at the same moment the values move, and it means the credentials that end up in `.env` have never been anywhere else.

The alternatives are moving them without rotating (fixes the source-literal problem, keeps a known-exposed password) or migrating as-is and handling it separately (fastest to cutover, leaves a public app with credentials in source).

**This needs the user's decision before Task 11 publishes the hostname.** If the answer is to move them, the change is: read `FILEVAULT_SECRET_KEY` and `FILEVAULT_ADMIN_PASSWORD` from the environment in `app.py`, add both to `/Volumes/T9/Projects/filevault/.env`, and add an `EnvironmentVariables` entry or a `.env` load to the agent. Re-run Step 4's smoke test afterwards.

---

### Task 9: Freeze and final delta

**First production-affecting step. Requires explicit go-ahead before starting.** From here the VPS pollers stop, and the Bluetooth gap begins — keep the window short.

**Files:**
- Modify: `db/amip.duckdb`, `db/speed.duckdb` on the Mac (final delta)

**Interfaces:**
- Consumes: Task 7's bulk transfer
- Produces: Mac databases byte-current with the VPS, and a recorded health baseline for Task 10 to match

- [ ] **Step 1: Record the VPS health baseline**

```bash
ssh amip "curl -s http://localhost:8000/api/health" | tee /tmp/vps-health-baseline.json
```

Expected: JSON with `status`, `hourly_rows`, `stations`, `latest_data`. Task 10 compares against this exact output.

- [ ] **Step 2: Stop the VPS writers**

```bash
ssh amip "sudo systemctl stop amip-bluetooth amip-refresh amip-watchdog.timer"
ssh amip "systemctl is-active amip-bluetooth amip-refresh || true"
```

Expected: both report `inactive`. The API stays running so the site keeps serving reads during the delta.

- [ ] **Step 3: Final delta of the two live databases**

```bash
cd "/Volumes/T9/Projects/Traffic Movement"
rsync -avh --progress amip:/opt/amip/db/amip.duckdb amip:/opt/amip/db/speed.duckdb db/
```

Expected: a short transfer — only the blocks changed since Task 7.

- [ ] **Step 4: Verify the delta landed**

```bash
echo "--- vps ---"; ssh amip "shasum /opt/amip/db/speed.duckdb"
echo "--- mac ---"; shasum db/speed.duckdb
```

Expected: identical checksums. `speed.duckdb` is the file the stopped poller was writing, so it is the one that must match exactly.

---

### Task 10: Start the stack on the Mac

**Files:** none — operational

**Interfaces:**
- Consumes: Tasks 1–9 (code, plists, venvs, env, tunnel config, data)
- Produces: seven running agents serving on `127.0.0.1:8000` and `127.0.0.1:5050`

- [ ] **Step 1: Remove the stale bluetooth-archive agent**

The old plist points at the pre-move `/Users/doug/Projects` path and has been dead since 2026-03-27. Task 2's generated agent replaces it.

```bash
launchctl bootout gui/$(id -u)/com.amip.bluetooth-archive 2>/dev/null || true
rm -f ~/Library/LaunchAgents/com.amip.bluetooth-archive.plist
```

Then re-link, since Task 2's installer wrote a symlink of the same name:

```bash
bash deploy/launchd/install.sh
```

- [ ] **Step 2: Load all seven agents**

```bash
cd "/Volumes/T9/Projects/Traffic Movement"
bash deploy/launchd/install.sh --load
```

- [ ] **Step 3: Verify every agent is loaded and running**

```bash
launchctl list | grep com.amip
```

Expected: seven rows. The first column is the PID — a number means running, `-` means loaded but not currently running (correct only for `com.amip.watchdog`, which is interval-driven). The second column is the last exit status; anything non-zero on a KeepAlive agent means it is crash-looping, so check its log in `logs/<label>.log`.

- [ ] **Step 4: Verify health parity against the VPS baseline**

```bash
curl -s http://localhost:8000/api/health | tee /tmp/mac-health.json
echo "--- baseline ---"; cat /tmp/vps-health-baseline.json
```

Expected: `hourly_rows` and `stations` match the baseline recorded in Task 9 exactly. `latest_data` matches too. A mismatch means the delta rsync did not land — do not proceed to DNS.

- [ ] **Step 5: Verify the Bluetooth poller is writing again**

```bash
sleep 360
./venv/bin/python3 -c "
import duckdb
con = duckdb.connect('db/speed.duckdb', read_only=True)
print('latest:', con.execute('SELECT max(ts_interval) FROM speed_observations').fetchone()[0])
print('rows:',   con.execute('SELECT count(*) FROM speed_observations').fetchone()[0])
con.close()
"
```

Expected: a timestamp newer than the freeze in Task 9, confirming the gap has closed and polling resumed on the Mac.

- [ ] **Step 6: Verify filevault is serving locally**

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5050/
```

Expected: `302` or `200`.

- [ ] **Step 7: Verify the watchdog reports healthy**

```bash
./venv/bin/python3 scripts/watchdog.py --check-only --verbose
```

Expected: `service/com.amip.api`, `service/com.amip.bluetooth` and `service/com.amip.refresh` all `OK`. The API and frontend checks will still fail — they point at `api.melbtraffic.com`, which has no DNS until Task 11. That is expected here.

---

### Task 11: Publish DNS and repoint the frontend

**Files:**
- Modify: Cloudflare Pages project environment variable (dashboard)

**Interfaces:**
- Consumes: Task 6's tunnel, Task 10's running stack
- Produces: `api.melbtraffic.com` and `files.melbtraffic.com` resolving to the Mac; frontend calling the new API base

- [ ] **Step 1: Publish both DNS routes**

`cloudflared` writes the CNAME records directly — no dashboard step needed.

```bash
cloudflared tunnel route dns melbtraffic api.melbtraffic.com
cloudflared tunnel route dns melbtraffic files.melbtraffic.com
```

Expected: confirmation for each, naming the `<uuid>.cfargotunnel.com` target.

- [ ] **Step 2: Verify DNS resolves and the tunnel answers**

```bash
dig +short api.melbtraffic.com
curl -s https://api.melbtraffic.com/api/health
curl -s -o /dev/null -w "%{http_code}\n" https://files.melbtraffic.com/
```

Expected: Cloudflare proxy IPs from `dig`; the same health JSON as `localhost:8000` returned; `302` or `200` from filevault. If the health call returns Cloudflare error 1033, the tunnel agent is not running — check `logs/com.amip.tunnel.log`.

- [ ] **Step 3: Update the Pages environment variable**

**User action:** Cloudflare Dashboard → Workers & Pages → the `traffic-movement` project → Settings → Environment variables → set `VITE_API_URL` to `https://api.melbtraffic.com` for Production, then Save.

`VITE_API_URL` is read at build time (`frontend/src/constants/index.js:5`), so the value only takes effect on the next build.

- [ ] **Step 4: Trigger a rebuild**

**User action:** Deployments → Retry deployment on the latest build, or push any commit to `main`.

- [ ] **Step 5: Verify the deployed frontend calls the new API**

```bash
curl -s https://melbtraffic.com/assets/*.js 2>/dev/null | grep -o "https://api\.melbtraffic\.com" | head -1
```

Expected: the new API base appears in the built bundle. If it still shows `melbtraffic.duckdns.org`, the rebuild has not finished or the variable was set on the wrong environment.

- [ ] **Step 6: Verify the site end to end in a browser**

**User action:** open `https://melbtraffic.com`, confirm charts render with live data, and check the browser console for CORS errors. A CORS failure here means `CORS_ORIGINS` from Task 4 did not reach the API — restart `com.amip.api` and re-check.

---

### Task 12: Reboot test

The single most important verification. Everything else can be true while the stack still fails to come back on its own — which is exactly the failure the user would discover after a power cut, days later.

**Files:** none

**Interfaces:**
- Consumes: Tasks 5, 10, 11
- Produces: proof of unattended recovery, or a documented reason it cannot happen

- [ ] **Step 1: Note what should come back**

```bash
launchctl list | grep com.amip > /tmp/pre-reboot-agents.txt
cat /tmp/pre-reboot-agents.txt
```

- [ ] **Step 2: Reboot**

**User action:** `sudo reboot`. Do not log in manually — the point is to prove automatic login and the agents recover without a human. If FileVault was found On in Task 5 Step 3, this test cannot pass unattended; enter the unlock password and record that the limitation is real.

- [ ] **Step 3: After the Mac comes back, verify without touching anything**

```bash
launchctl list | grep com.amip
curl -s https://api.melbtraffic.com/api/health
```

Expected: the same seven agents with fresh PIDs, and the public health endpoint answering. This proves T9 mounted, the PathState guards released, the agents started, and the tunnel reconnected — with no intervention.

- [ ] **Step 4: Verify the volume guard actually works**

Confirm the PathState mechanism does what Task 2 claims, rather than assuming it:

```bash
launchctl list | grep com.amip.api          # note the PID
diskutil unmount /Volumes/T9
sleep 10
launchctl list | grep com.amip.api          # expect no PID, or absent
diskutil mount /Volumes/T9
sleep 20
launchctl list | grep com.amip.api          # expect a new PID
curl -s http://localhost:8000/api/health
```

Expected: the agent stops while the volume is away and restarts on remount. If it instead crash-loops with a non-zero exit status while unmounted, the guard path in `generate.py` is wrong — fix and regenerate before relying on it.

---

### Task 13: Soak and final verification

**Files:** none

**Interfaces:**
- Consumes: everything prior
- Produces: the evidence needed to justify cancelling the VPS

- [ ] **Step 1: Let it run for 24–48 hours**

The VPS stays powered with its writers stopped, as a hot standby. Do not cancel it yet.

- [ ] **Step 2: Verify polling has no gaps across the soak**

```bash
cd "/Volumes/T9/Projects/Traffic Movement"
./venv/bin/python3 -c "
import duckdb
con = duckdb.connect('db/speed.duckdb', read_only=True)
rows = con.execute('''
    SELECT date_trunc('hour', ts_interval) AS hr, count(*) AS n
    FROM speed_observations
    WHERE ts_interval > now() - INTERVAL 24 HOUR
    GROUP BY 1 ORDER BY 1
''').fetchall()
for hr, n in rows:
    print(f'  {hr}  {n}')
print(f'{len(rows)} hours covered (expect 24)')
con.close()
"
```

Expected: 24 hours, each with a similar row count. A missing or thin hour means the poller stalled — check `logs/com.amip.bluetooth.log`.

- [ ] **Step 3: Verify the archive poller resumed**

```bash
./venv/bin/python3 -c "
import duckdb
con = duckdb.connect('archive-poller/bluetooth_archive.duckdb', read_only=True)
print('rows:', con.execute('SELECT count(*) FROM speed_log').fetchone()[0])
print('latest:', con.execute('SELECT max(ts) FROM speed_log').fetchone()[0])
con.close()
"
```

Expected: a recent `latest`. There is a five-month hole from 2026-03-27 (when the volume move killed the old agent) to cutover — expected, and backfillable from `speed.duckdb` if wanted, since that covered the period continuously.

- [ ] **Step 4: Verify the daily refresh ran on schedule**

`daily_refresh.py` runs at 4am and 5pm AEST and orchestrates `archive_speed.py` and `backup_db.py`.

```bash
tail -40 logs/com.amip.refresh.log
ls -lt db/backups/ | head -5
```

Expected: a completed refresh cycle in the log, and a backup file newer than cutover — confirming backups are running on the Mac.

- [ ] **Step 5: Verify two consecutive clean watchdog cycles**

```bash
tail -60 logs/com.amip.watchdog.log
```

Expected: two runs 15 minutes apart with all services `OK` and the API and frontend checks now passing against the melbtraffic.com hostnames.

- [ ] **Step 6: Resolve the orphaned WAL file**

`db/amip_fresh.duckdb.wal` (1.7 MB) has no matching database and predates the migration.

```bash
ls -la db/amip_fresh.duckdb*
```

If no `amip_fresh.duckdb` exists, it is a leftover from an interrupted operation and can be removed. Confirm with the user before deleting.

---

### Task 14: Decommission and document

Only after Task 13 passes in full.

**Files:**
- Modify: `DEPLOY.md`
- Modify: `RUNTIME.md` (stale `/Users/doug/Projects/Traffic Movement` paths throughout)

**Interfaces:**
- Consumes: a verified Mac stack
- Produces: documentation matching reality, and a cancelled VPS

- [ ] **Step 1: Take a final full backup of the VPS**

Belt and braces before anything is destroyed.

```bash
cd "/Volumes/T9/Projects/Traffic Movement"
rsync -avh amip:/opt/amip/ db/backups/vps-final-snapshot-$(date +%Y%m%d)/
ssh amip "sudo tar czf - /opt/filevault" > db/backups/filevault-final-$(date +%Y%m%d).tar.gz
```

- [ ] **Step 2: Rewrite `DEPLOY.md` for the local topology**

Replace the VPS provisioning content with: the launchd architecture diagram from the spec, how to start and stop agents (`launchctl bootout` / `bootstrap` via `deploy/launchd/install.sh`), how to regenerate plists after a path change (`python3 deploy/launchd/generate.py`), where logs live (`logs/<label>.log`), how the tunnel is configured, and how to restore from `db/backups/`. Delete the Contabo, Caddy, DuckDNS and systemd sections.

- [ ] **Step 3: Fix the stale paths in `RUNTIME.md`**

Every path reads `/Users/doug/Projects/Traffic Movement`; the project is at `/Volumes/T9/Projects/Traffic Movement`. Update them, and replace the `pip3 install --break-system-packages` guidance with the venv from Task 3.

- [ ] **Step 4: Commit the documentation**

```bash
git add DEPLOY.md RUNTIME.md
git commit -m "docs: rewrite deployment docs for local Mac topology

Replaces the Contabo/Caddy/systemd runbook with the launchd + Cloudflare
Tunnel setup, and corrects the pre-volume-move paths in RUNTIME.md."
```

- [ ] **Step 5: Cancel the VPS**

**User action, irreversible.** Confirm one last time that `https://melbtraffic.com` and `https://files.melbtraffic.com` are both serving from the Mac, then cancel the Contabo subscription and remove the `amip` host block from `~/.ssh/config`.

The DuckDNS hostnames `melbtraffic.duckdns.org` and `softfiles.duckdns.org` can be released at the same time.

---

## Self-Review

**Spec coverage:** §2 architecture → Tasks 2, 6, 10, 11. §3 decisions D1/D10 → Task 6; D2 → Tasks 8, 14; D3 → Task 7; D4 → Tasks 2, 10 Step 1; D5 → Task 5; D6/D7 → Task 2; D8/D9 → Tasks 3, 8. §5 macOS concerns → Tasks 5, 12. §6 code changes → Tasks 1 (watchdog), 2 (plists), 4 (.env), 11 (Pages), 14 (docs). §7 cutover → Tasks 7–11. §8 verification → Tasks 10, 12, 13. §9 risks → guard tested in Task 12 Step 4, stale DB in Task 7 Step 1, encryption in Task 5 Step 3, credentials in Task 8 Step 5, tunnel credentials backed up in Task 6 Step 7. §10 open question → Task 8 Step 5.

**Type consistency:** `get_controller(platform=None)`, `is_active(service_id)`, `start(service_id)`, `platform_key`, `service_ids(controller)`, `SERVICE_IDS`, `SERVICE_ORDER` — defined in Task 1 Step 3, exercised in Task 1 Step 1's tests, consumed in Task 1 Step 5. Agent labels are identical across `generate.py`, `install.sh`, `SERVICE_IDS` and every verification command.

**Known deviation from strict TDD:** only Task 1 has a red-green cycle. Tasks 2–14 are infrastructure and data movement, where the equivalent discipline is a verification step with an explicit expected result before moving on — which every task carries.
