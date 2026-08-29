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
