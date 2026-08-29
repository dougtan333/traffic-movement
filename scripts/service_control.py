"""
service_control.py — Platform-agnostic service supervision

The watchdog asks three questions of the host's init system: "what state is
this service in?", "start it" and "stop it". systemd answers them on the Linux
VPS, launchd on the Mac. This module is the only place in the codebase that
knows which.

Adding a service means adding one row to SERVICE_IDS — the logical name the
caller uses, mapped to the identifier each platform expects.

State, not just a boolean
-------------------------
`is_active()` answers yes/no, but "no" covers two very different situations:
the job is registered with the supervisor and has stopped or crashed, or the
job was never registered at all (the plist could not be read at login, the
unit does not exist). Those need different responses from a human, so
`state()` reports which one it is and `describe_state()` puts it in words the
watchdog log can carry. See finding I7.

`start()` and `stop()` return the real success of the subprocess, so a caller
that cannot restart a service finds out instead of being told True
unconditionally.

Consumed by: scripts/watchdog.py, scripts/daily_refresh.py
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

# Service states, normalised across platforms.
STATE_RUNNING = "running"        # supervisor reports a live process
STATE_STOPPED = "stopped"        # registered with the supervisor, not running
STATE_FAILED = "failed"          # registered, and the supervisor calls it failed
STATE_NOT_LOADED = "not-loaded"  # the supervisor has never heard of it
STATE_UNKNOWN = "unknown"        # the query itself did not answer usefully

# Human-readable form of each state, for logs read at 2am.
STATE_DESCRIPTIONS = {
    STATE_RUNNING: "running",
    STATE_STOPPED: "loaded but not running",
    STATE_FAILED: "loaded and reported as failed",
    STATE_NOT_LOADED: "NOT LOADED — the supervisor has no such job "
                      "(on macOS, run deploy/launchd/install.sh --load)",
    STATE_UNKNOWN: "state could not be determined",
}


def describe_state(state):
    """One-line English for a state constant, for the watchdog's log line."""
    return STATE_DESCRIPTIONS.get(state, f"unrecognised state {state!r}")


class SystemdController:
    """Service control via systemctl. Used on the Linux VPS."""

    platform_key = "systemd"

    def state(self, service_id):
        """Normalised state from `systemctl is-active`.

        systemctl prints the state word on stdout regardless of exit code:
        `active`, `inactive`, `failed`, or `unknown` for a unit that does not
        exist — which is systemd's equivalent of launchd's not-loaded.
        """
        r = subprocess.run(["systemctl", "is-active", service_id],
                           capture_output=True, text=True, timeout=5)
        raw = r.stdout.strip()
        if raw == "active":
            return STATE_RUNNING
        if raw == "inactive":
            return STATE_STOPPED
        if raw == "failed":
            return STATE_FAILED
        if raw == "unknown":
            return STATE_NOT_LOADED
        return STATE_UNKNOWN

    def is_active(self, service_id):
        """True when systemctl reports the unit as active."""
        return self.state(service_id) == STATE_RUNNING

    def start(self, service_id):
        """Start the unit. Requires passwordless sudo, as configured on the VPS.

        Returns True only when systemctl exited 0.
        """
        r = subprocess.run(["sudo", "-n", "systemctl", "start", service_id],
                           capture_output=True, timeout=10)
        return r.returncode == 0

    def stop(self, service_id):
        """Stop the unit. Returns True only when systemctl exited 0."""
        r = subprocess.run(["sudo", "-n", "systemctl", "stop", service_id],
                           capture_output=True, timeout=10)
        return r.returncode == 0


class LaunchdController:
    """Service control via launchctl. Used on macOS.

    `launchctl list <label>` exits non-zero (113) when the job is not loaded at
    all, and prints a plist fragment containing a `"PID" = <n>;` line only while
    the job is actually running — a loaded-but-stopped job has no PID key. Both
    cases mean "not active", but only one of them can be fixed by a kickstart,
    which is why `state()` keeps them apart.

    `stop()` sends SIGTERM via `launchctl kill`. Note that the AMIP agents carry
    a KeepAlive PathState guard, so launchd relaunches a killed job once its
    ThrottleInterval (10s) elapses and the guard path is present. `stop()`
    therefore buys a window, not an indefinite shutdown.
    """

    platform_key = "launchd"

    def _target(self, service_id):
        """The GUI-domain service target launchctl subcommands take."""
        return f"gui/{os.getuid()}/{service_id}"

    def state(self, service_id):
        """Normalised state from `launchctl list <label>`."""
        r = subprocess.run(["launchctl", "list", service_id],
                           capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return STATE_NOT_LOADED
        return STATE_RUNNING if '"PID" =' in r.stdout else STATE_STOPPED

    def is_active(self, service_id):
        """True when launchctl reports a live PID for the label."""
        return self.state(service_id) == STATE_RUNNING

    def start(self, service_id):
        """Kickstart the agent in the current user's GUI domain.

        Returns True only when launchctl exited 0. Kickstarting a label that was
        never loaded exits 113 with "Could not find service ... in domain for
        user"; that used to be discarded.
        """
        r = subprocess.run(["launchctl", "kickstart", self._target(service_id)],
                           capture_output=True, timeout=10)
        return r.returncode == 0

    def stop(self, service_id):
        """Send SIGTERM to the agent. Returns True only when launchctl exited 0."""
        r = subprocess.run(["launchctl", "kill", "TERM", self._target(service_id)],
                           capture_output=True, timeout=10)
        return r.returncode == 0


def get_controller(platform=None):
    """Return the controller for this platform.

    `platform` is overridable so tests can exercise both branches on one host.
    """
    plat = platform if platform is not None else sys.platform
    return LaunchdController() if plat == "darwin" else SystemdController()


def service_ids(controller):
    """The platform-specific identifiers, in the watchdog's reporting order."""
    return [SERVICE_IDS[name][controller.platform_key] for name in SERVICE_ORDER]


def service_id_for(controller, logical_name):
    """The identifier this platform uses for one logical service name.

    Callers that supervise a single named service (daily_refresh.py and the
    Bluetooth poller) go through this rather than indexing SERVICE_IDS by hand,
    so an unknown name fails loudly instead of raising a bare KeyError.
    """
    try:
        return SERVICE_IDS[logical_name][controller.platform_key]
    except KeyError:
        raise KeyError(
            f"No service id for {logical_name!r} on {controller.platform_key}; "
            f"known names: {', '.join(sorted(SERVICE_IDS))}"
        )
