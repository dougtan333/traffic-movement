# VPS → Mac Migration — Design

**Date:** 2026-08-29
**Status:** Approved for planning
**Goal:** Retire the Contabo VPS (~€7.50/mo) by moving the melbtraffic.com API, its
pollers, and the filevault document server onto the always-on Mac, with no loss of
data and only a minutes-long gap in Bluetooth polling.

---

## 1. Current state (measured 2026-08-29)

### VPS — Contabo, `161.97.152.11`, user `amip`, code at `/opt/amip`

| Unit | Role |
|---|---|
| `amip-api.service` | uvicorn `api.main:app` on `127.0.0.1:8000` |
| `amip-bluetooth.service` | `scripts/poll_bluetooth.py --loop` — 5-minute cadence |
| `amip-refresh.service` | `scripts/daily_refresh.py --loop` — 4am + 5pm AEST |
| `amip-watchdog.timer` | `scripts/watchdog.py --verbose` every 15 min, oneshot |
| `caddy.service` | TLS + reverse proxy |
| `filevault.service` | `gunicorn -w 4 -b 127.0.0.1:5050 app:app`, user `filevault`, `/opt/filevault` |

Caddyfile routes `melbtraffic.duckdns.org` → `:8000` and `softfiles.duckdns.org` → `:5050`.

`daily_refresh.py` already orchestrates `archive_speed.py` and `backup_db.py`, so
archiving and backups need no separate scheduling after the move.

### Data on the VPS

| Path | Size |
|---|---|
| `/opt/amip/db/amip.duckdb` | 4.1 GB |
| `/opt/amip/db/speed.duckdb` | 2.4 GB |
| `/opt/amip/db/archive` | 11 GB |
| `/opt/amip/db/backups` | 29 GB |
| `/opt/filevault` | 23 MB (22.9 MB is its venv — see below) |
| `/opt/filevault/uploads` — **live document store** | 32 KB, 2 files |
| `/home/amip/doc-repository` | 52 KB — install source, `uploads/` empty |

Total ≈ 46.5 GB. The VPS is the source of truth; the local copies are stale
(`db/amip.duckdb` is 269 MB, dated March).

**filevault storage — resolved 2026-08-29.** `app.py` line 39 sets
`UPLOAD_FOLDER = <app dir>/uploads`, so the live store is `/opt/filevault/uploads`:
32 KB across two files (a `.docx` and `.md` of the same stakeholder meeting notes).
`/home/amip/doc-repository` is the *install source* the app was deployed from — same
`app.py`, empty `uploads/`. Of filevault's 23 MB, 22.9 MB is its venv, which is
rebuilt on the Mac. The real payload to migrate is roughly 56 KB: `app.py`,
`templates/`, `requirements.txt` and the two uploaded documents.

### Mac

- Project at `/Volumes/T9/Projects/Traffic Movement` (external volume, 309 GB free of 931 GB)
- Python 3.14.4, no project venv, `tailscale` present, no `cloudflared`, no `caddy`
- `~/Library/LaunchAgents/com.amip.bluetooth-archive.plist` points at the pre-move path
  `/Users/doug/Projects/Traffic Movement` and has been dead since its last log line,
  `2026-03-27 17:45`
- Other projects on this Mac already use the LaunchAgent + KeepAlive pattern

### DNS

`melbtraffic.com` is on Cloudflare nameservers (`sandy`/`kayden.ns.cloudflare.com`),
apex proxied (`104.21.75.82`, `172.67.217.147`). The frontend is on Cloudflare Pages
and reads its API base from the `VITE_API_URL` build-time variable
(`frontend/src/constants/index.js`).

### Portability

Every DB path in `api/db.py`, `scripts/poll_bluetooth.py`, `scripts/watchdog.py` and
`scripts/archive_speed.py` resolves from `PROJECT_ROOT`. Nothing is hardcoded to
`/opt/amip`. The single OS-specific dependency in the codebase is `watchdog.py`,
which shells out to `systemctl` (lines 95, 109, 113).

---

## 2. Target architecture

```
Cloudflare (free)                      Mac — /Volumes/T9/Projects/Traffic Movement
┌──────────────────────────┐           ┌──────────────────────────────────────────┐
│ Pages: melbtraffic.com   │           │ cloudflared           (KeepAlive)        │
│   VITE_API_URL =         │           │   api.melbtraffic.com    → :8000         │
│   https://api.melbtraffic│ ←─tunnel─ │   files.melbtraffic.com  → :5050         │
│      .com                │ (outbound │ uvicorn api.main:app       :8000         │
│                          │   only)   │ gunicorn filevault app     :5050         │
│ DNS: CNAME api, files    │           │ poll_bluetooth.py --loop     (5 min)     │
│      → <uuid>.cfargotun… │           │ daily_refresh.py --loop      (4am/5pm)   │
└──────────────────────────┘           │ bluetooth_archive.py --loop  (5 min)     │
                                       │ watchdog.py                  (15 min)    │
                                       │ DuckDB + archive + backups on T9         │
                                       └──────────────────────────────────────────┘
```

Retired: Contabo, Caddy, DuckDNS, and both `*.duckdns.org` hostnames.

### Why Cloudflare Tunnel

The Mac opens an outbound connection to Cloudflare's edge; no inbound ports, no
router configuration, no exposed home IP, and it works behind CGNAT. DNS is already
at Cloudflare, so publishing a hostname is a single record. `cloudflared` performs
the hostname→port mapping itself, which removes the need for Caddy on the Mac.

Rejected: **port-forward + Caddy + DuckDNS** (requires a non-CGNAT public IP, opens
ports on the home network, exposes the home IP) and **Tailscale Funnel** (serves only
`*.ts.net` hostnames, so it cannot front `melbtraffic.com` without a proxy hack).

### Why `api.melbtraffic.com` rather than reusing the DuckDNS name

Naming the API under the owned domain decouples the API address from its host, so a
future move needs a DNS change rather than a frontend rebuild. It also lets DuckDNS
be dropped entirely.

---

## 3. Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Cloudflare Tunnel for ingress | No inbound ports, CGNAT-safe, free, DNS already at Cloudflare |
| D2 | Migrate filevault too; cancel the VPS outright | 23 MB of code and a small document store; nothing else depends on the VPS |
| D3 | Transfer all ~46.5 GB including `db/backups` | T9 has room; backup history is not regenerable |
| D4 | Repoint `com.amip.bluetooth-archive` at the T9 path and keep it running | It is an independent redundant archive, not a duplicate of `archive_speed.py` |
| D5 | ~~Enable automatic login~~ **Superseded 2026-08-29: keep FileVault on, accept manual unlock** | `fdesetup status` returned On. macOS does not offer auto-login while FileVault is enabled — the volume needs a human before any login, so no agent runs until then. The disk holds live API keys and ~46 GB of data, and downtime is acceptable on this project, so encryption wins. Planned reboots use `sudo fdesetup authrestart`; an unplanned power cut means downtime until the Mac is unlocked by hand. |
| D11 | filevault credentials move to `.env` **and** are rotated | Decided 2026-08-29. The old password sat in plaintext in a file read during this migration, and the app becomes publicly reachable again at a new hostname. |
| D6 | LaunchAgents, not LaunchDaemons | Consistent with the Mac's existing projects; avoids root and pre-login volume-mount ordering |
| D7 | Plists version-controlled in `deploy/launchd/`, symlinked into `~/Library/LaunchAgents` | The current untracked plist drifted into a stale path unnoticed |
| D8 | Project venv at `venv/`, separate venv for filevault | Removes `--break-system-packages`; preserves filevault's isolation from the VPS |
| D9 | filevault lands at `/Volumes/T9/Projects/filevault`, its own directory | It is a separate application; nesting it inside the traffic repo would confuse both |
| D10 | Tunnel named `melbtraffic` | One named tunnel serves both hostnames; its generated UUID is the CNAME target for each |

---

## 4. Components — LaunchAgents

All plists live in `deploy/launchd/` and are symlinked into `~/Library/LaunchAgents`.

| Label | Program | Restart policy |
|---|---|---|
| `com.amip.api` | `venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000` | KeepAlive |
| `com.amip.bluetooth` | `venv/bin/python scripts/poll_bluetooth.py --loop` | KeepAlive |
| `com.amip.refresh` | `venv/bin/python scripts/daily_refresh.py --loop` | KeepAlive |
| `com.amip.filevault` | `filevault-venv/bin/gunicorn -w 4 -b 127.0.0.1:5050 app:app` | KeepAlive |
| `com.amip.tunnel` | `cloudflared tunnel run melbtraffic` | KeepAlive |
| `com.amip.bluetooth-archive` | `archive-poller/bluetooth_archive.py --loop` | KeepAlive (repointed) |
| `com.amip.watchdog` | `venv/bin/python scripts/watchdog.py --verbose` | `StartInterval 900`, oneshot |

Each carries `EnvironmentVariables: PYTHONUNBUFFERED=1` and sends stdout/stderr to a
log file. The six AMIP agents use `WorkingDirectory /Volumes/T9/Projects/Traffic
Movement`; `com.amip.filevault` uses `/Volumes/T9/Projects/filevault` and guards on
its own path rather than on `amip.duckdb` (see §5).

---

## 5. macOS-specific concerns

### Sleep

Measured 2026-08-29: `sleep 0`, `standby 0` and `disksleep 0` are **already set** on
this Mac, so the poller is not currently at risk of sleep-induced holes. The only
outstanding change is power-failure recovery:

`sudo pmset -a autorestart 1`   *(currently 0)*

`autopoweroff` is not exposed on this machine and must be omitted — including it makes
`pmset` reject the whole command.

### External volume mount ordering

LaunchAgents can fire before `/Volumes/T9` mounts, starting every service against a
missing database. Each plist therefore uses:

```
KeepAlive → PathState → "/Volumes/T9/Projects/Traffic Movement/db/amip.duckdb" = true
```

launchd runs the job only while that path exists and starts it automatically when the
drive appears — no polling wrapper script. `com.amip.bluetooth-archive` uses the same
guard against its own DB path.

### Boot without login

LaunchAgents start at login. Automatic login is **not currently enabled** (verified
2026-08-29: `com.apple.loginwindow autoLoginUser` is unset), so enabling it is a real
step, not a no-op. With D5 applied, an unattended reboot restores the full stack.

Note the interaction with FileVault disk encryption: if the boot volume is encrypted,
macOS requires the unlock password at startup and automatic login cannot proceed until
that is entered. This must be checked during pre-stage — if the disk is encrypted,
unattended reboot recovery does not work regardless of the auto-login setting.

---

## 6. Code changes

Five touchpoints, deliberately small.

1. **`scripts/watchdog.py`** — two changes:
   - Extract a service-control layer exposing `is_active(name)` and `start(name)`, with
     a systemd implementation (`systemctl`) and a launchd one (`launchctl print` /
     `launchctl kickstart`), selected on `sys.platform`. The freshness, API-endpoint and
     frontend checks are already portable and are unchanged.
   - Update the hardcoded constants at lines 40–44: `API_BASE` from
     `https://melbtraffic.duckdns.org` to `https://api.melbtraffic.com`, `FRONTEND_URL`
     from `https://traffic-movement.pages.dev` to `https://melbtraffic.com`, and
     `SERVICES` from the systemd names to the launchd labels.

2. **`deploy/launchd/*.plist`** — seven new files, per the table above.

3. **Cloudflare Pages** — `VITE_API_URL` → `https://api.melbtraffic.com`, then redeploy.

4. **`.env` reconciliation** — the local `.env` holds only `VIC_BLUETOOTH_API_KEY`,
   `SERVO_SAVER_CONSUMER_ID` and `EIA_API_KEY`. The VPS additionally sets
   `CORS_ORIGINS` and `AMIP_DEBUG=false`. `CORS_ORIGINS` must be carried across, or the
   Mac's API will reject the production frontend. Target value:
   `https://melbtraffic.com,https://www.melbtraffic.com,https://traffic-movement.pages.dev`.

5. **`DEPLOY.md`** — rewritten for the local topology; VPS provisioning content removed.

---

## 7. Cutover plan

Bulk-first, so the polling gap is minutes rather than hours. The site stays up
through steps 1–2.

1. **Pre-stage (VPS still serving)**
   - Install `cloudflared` (`brew install cloudflared` — formula confirmed available;
     Homebrew 6.0.11 present at `/opt/homebrew/bin/brew`); create and authenticate the
     `melbtraffic` tunnel
   - `sudo pmset -a autorestart 1`; enable automatic login; confirm boot-volume
     encryption state
   - Build `venv/` and the filevault venv
   - ~~Locate filevault's document storage~~ — **resolved, see §1**: copy
     `/opt/filevault/{app.py,templates,requirements.txt,uploads}` (~56 KB); the venv is
     rebuilt locally and `~/doc-repository` is a redundant install source
   - Reconcile `.env` (add `CORS_ORIGINS`, `AMIP_DEBUG`) from the VPS copy
   - `rsync` all ~46.5 GB down to T9, and `/opt/filevault` to
     `/Volumes/T9/Projects/filevault`
2. **Freeze**
   - Stop `amip-bluetooth`, `amip-refresh`, `amip-watchdog.timer` on the VPS
   - Record `/api/health` row counts from the VPS
   - Final `rsync` delta of `amip.duckdb` and `speed.duckdb`
3. **Start on the Mac**
   - Load all seven LaunchAgents
   - Confirm local `/api/health` row counts match the recorded VPS values
4. **Switch DNS**
   - CNAME `api.melbtraffic.com` and `files.melbtraffic.com` to the tunnel
   - Update the Pages `VITE_API_URL` and redeploy the frontend
5. **Soak 24–48 h** with the VPS powered but idle as a hot standby
6. **Cancel Contabo**

---

## 8. Verification

Before cancelling the VPS, all of the following must hold:

- `/api/health` row counts on the Mac equal the values recorded from the VPS at freeze
- `max(timestamp)` in `speed_observations` advances across successive 5-minute polls
- `bluetooth_archive.duckdb` row count advances
- `watchdog.py` reports green across two consecutive 15-minute cycles
- `https://api.melbtraffic.com/api/health` and `https://files.melbtraffic.com` both
  serve over the tunnel
- melbtraffic.com renders with live data from the new API base, with no CORS errors
  in the browser console
- A deliberate Mac reboot restores every service unattended, with no manual step

---

## 9. Risks

| Risk | Mitigation |
|---|---|
| T9 unmounts while services run | `KeepAlive → PathState` stops jobs cleanly and restarts them on remount |
| Home internet or power outage takes the site down | Accepted — downtime is tolerable for this project (user decision) |
| Bluetooth polling gap during freeze | Freeze window is minutes; gap is bounded and visible in `speed_observations` |
| `bluetooth_archive.duckdb` has a gap from 2026-03-27 to cutover | Unrecoverable from the API (latest-only), but `speed.duckdb` covers the period and can backfill the archive if wanted |
| Stale local `db/amip.duckdb` (269 MB, March) overwritten or confused with the real one | Move it aside before the rsync rather than letting rsync merge into it |
| ~~filevault storage location misidentified~~ | **Resolved 2026-08-29** — `/opt/filevault/uploads`, 2 files, 32 KB (§1) |
| Boot volume encrypted, so auto-login cannot complete after an unattended reboot | Encryption state checked during pre-stage; if encrypted, unattended recovery is not achievable and downtime after a power cut lasts until manual unlock |
| filevault credentials are hardcoded in `app.py` and the app becomes publicly reachable again at a new hostname | Flagged as an open question below — moving them to `.env` is a small change but alters app behaviour, so it needs a decision rather than a silent fix |
| Cloudflare Tunnel token/credentials lost | Tunnel credentials backed up alongside `.env`; recreating a tunnel is a DNS change |

---

## 10. Open question — filevault credentials

`/opt/filevault/app.py` hardcodes both the Flask `secret_key` and an `admin` password
as literals in source (lines 34 and 53). The file is not in git, which is the only
reason this has not been committed to a repository so far.

The migration republishes this app at `files.melbtraffic.com`, so it is the natural
moment to move both values into `.env` alongside the other secrets — but that changes
app behaviour and the credentials themselves, so it is not something to fold in
silently. Three options: move them to `.env` as part of the migration, move them and
also rotate them, or migrate as-is and handle it separately.

**This needs a decision before filevault is republished.**

---

## 11. Out of scope

- Any change to the Cloudflare Pages frontend beyond the API base URL
- Schema, query or ingestion-logic changes
- Backfilling the `bluetooth_archive.duckdb` gap (noted as optional follow-up)
- Rewriting filevault (moved as-is; it is not in git and stays that way for now)
- Backfilling filevault into version control
