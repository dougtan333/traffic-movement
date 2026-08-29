
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