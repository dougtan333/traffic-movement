"""
test_service_control.py — Unit tests for the platform service-control layer.

Replaces subprocess.run with a fake so the tests never touch real systemd or
launchd. Verifies both controllers issue the right commands, read their
output correctly, report a distinguishable state (running / stopped /
failed / not-loaded) and return honest success booleans from start/stop.

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


def test_systemd_state():
    """is-active prints the state word on stdout whatever its exit code."""
    c = service_control.SystemdController()

    fake = FakeRun(stdout="active\n")
    check("systemd state active", with_fake_run(fake, lambda: c.state("amip-api")),
          service_control.STATE_RUNNING)

    fake = FakeRun(stdout="inactive\n")
    check("systemd state inactive", with_fake_run(fake, lambda: c.state("amip-api")),
          service_control.STATE_STOPPED)

    fake = FakeRun(stdout="failed\n")
    check("systemd state failed", with_fake_run(fake, lambda: c.state("amip-api")),
          service_control.STATE_FAILED)

    # systemd's equivalent of launchd's "never loaded": no such unit.
    fake = FakeRun(stdout="unknown\n", returncode=4)
    check("systemd state unknown-unit -> not-loaded",
          with_fake_run(fake, lambda: c.state("amip-api")),
          service_control.STATE_NOT_LOADED)


def test_systemd_start():
    c = service_control.SystemdController()
    fake = FakeRun()
    ok = with_fake_run(fake, lambda: c.start("amip-refresh"))
    check("systemd start command", fake.calls[0],
          ["sudo", "-n", "systemctl", "start", "amip-refresh"])
    check("systemd start rc=0 -> True", ok, True)

    # sudo -n with no cached credential exits 1 before systemctl is reached.
    fake = FakeRun(returncode=1)
    check("systemd start rc=1 -> False",
          with_fake_run(fake, lambda: c.start("amip-refresh")), False)


def test_systemd_stop():
    c = service_control.SystemdController()
    fake = FakeRun()
    ok = with_fake_run(fake, lambda: c.stop("amip-bluetooth"))
    check("systemd stop command", fake.calls[0],
          ["sudo", "-n", "systemctl", "stop", "amip-bluetooth"])
    check("systemd stop rc=0 -> True", ok, True)

    fake = FakeRun(returncode=1)
    check("systemd stop rc=1 -> False",
          with_fake_run(fake, lambda: c.stop("amip-bluetooth")), False)


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


def test_launchd_state():
    """The watchdog must tell "never loaded" apart from "loaded but stopped"."""
    c = service_control.LaunchdController()

    fake = FakeRun(stdout='{\n\t"PID" = 4242;\n\t"Label" = "com.amip.api";\n}\n')
    check("launchd state running", with_fake_run(fake, lambda: c.state("com.amip.api")),
          service_control.STATE_RUNNING)

    fake = FakeRun(stdout='{\n\t"Label" = "com.amip.api";\n}\n')
    check("launchd state loaded-not-running",
          with_fake_run(fake, lambda: c.state("com.amip.api")),
          service_control.STATE_STOPPED)

    # `launchctl list <unloaded label>` exits 113 and prints nothing useful.
    fake = FakeRun(stdout="", returncode=113)
    check("launchd state not-loaded",
          with_fake_run(fake, lambda: c.state("com.amip.api")),
          service_control.STATE_NOT_LOADED)


def test_launchd_start():
    c = service_control.LaunchdController()
    fake = FakeRun()
    ok = with_fake_run(fake, lambda: c.start("com.amip.bluetooth"))
    cmd = fake.calls[0]
    check("launchd kickstart verb", cmd[:2], ["launchctl", "kickstart"])
    check("launchd kickstart target shape", cmd[2].startswith("gui/"), True)
    check("launchd kickstart target label", cmd[2].endswith("/com.amip.bluetooth"), True)
    check("launchd start rc=0 -> True", ok, True)

    # Kickstarting a label that was never loaded exits 113.
    fake = FakeRun(returncode=113)
    check("launchd start rc=113 -> False",
          with_fake_run(fake, lambda: c.start("com.amip.bluetooth")), False)


def test_launchd_stop():
    c = service_control.LaunchdController()
    fake = FakeRun()
    ok = with_fake_run(fake, lambda: c.stop("com.amip.bluetooth"))
    cmd = fake.calls[0]
    check("launchd kill verb", cmd[:3], ["launchctl", "kill", "TERM"])
    check("launchd kill target shape", cmd[3].startswith("gui/"), True)
    check("launchd kill target label", cmd[3].endswith("/com.amip.bluetooth"), True)
    check("launchd stop rc=0 -> True", ok, True)

    fake = FakeRun(returncode=113)
    check("launchd stop rc=113 -> False",
          with_fake_run(fake, lambda: c.stop("com.amip.bluetooth")), False)


def test_describe_state():
    """The not-loaded wording is what tells an operator the disk never mounted."""
    check("not-loaded description is distinct",
          service_control.describe_state(service_control.STATE_NOT_LOADED)
          != service_control.describe_state(service_control.STATE_STOPPED), True)
    check("not-loaded description says so",
          "NOT LOADED" in service_control.describe_state(service_control.STATE_NOT_LOADED),
          True)


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


def test_service_id_for():
    """daily_refresh.py resolves the poller's id through this."""
    check("service_id_for launchd bluetooth",
          service_control.service_id_for(service_control.get_controller("darwin"), "bluetooth"),
          "com.amip.bluetooth")
    check("service_id_for systemd bluetooth",
          service_control.service_id_for(service_control.get_controller("linux"), "bluetooth"),
          "amip-bluetooth")

    try:
        service_control.service_id_for(service_control.get_controller("darwin"), "nope")
        raised = False
    except KeyError:
        raised = True
    check("service_id_for unknown name raises KeyError", raised, True)


def main():
    print("Service control layer tests\n")
    for fn in (test_systemd_is_active, test_systemd_state,
               test_systemd_start, test_systemd_stop,
               test_launchd_is_active, test_launchd_state,
               test_launchd_start, test_launchd_stop,
               test_describe_state,
               test_controller_selection, test_service_ids_per_platform,
               test_service_id_for):
        print(f"{fn.__name__}:")
        fn()
    print(f"\n  {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
