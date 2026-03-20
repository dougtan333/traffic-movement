# memory.md — Traffic Movement
> Persistent session notes. Updated at the end of every working session.

---

## Last updated
21 March 2026 — Metro core filtering, YoY comparison, labelling overhaul, daily refresh automation, DB compaction (7.7GB → 1.7GB).

---

## Settled decisions
- DuckDB confirmed as data layer (DEC-001)
- React JSX frontend (DEC-002), Recharts for charts (DEC-010)
- Modular architecture, 150 line soft limit (DEC-003)
- Victoria-only focus for all new data (DEC-016), NSW removed from dashboard (DEC-019)
- Metro core filter: P75+ stations (~967) on Monitor, daily counts, Analysis tabs (DEC-020)
- DB compaction via parquet export/reimport (DEC-021)
- Daily automated refresh for fuel/price data (DEC-022)
- Fuel crisis baseline: Feb 2026 weekday average (DEC-015)
- Full decisions log in `decisions.md`

---

## Current blockers / open threads
- Need fresh SCATS data (latest month) from VIC portal for continued fuel crisis tracking
- Patterns tab (heatmap, hourly profile, day-of-week) still uses full network — may want metro core too
- Old DB files still on disk: `db/amip_old.duckdb` (7.7GB) + `db/amip_export/` (446MB) — awaiting confirmation to delete
- Deployment planning outstanding (OPEN-004) — VPS $6–10/month viable with compacted DB
- Auth (OPEN-001) and payments (OPEN-002) deferred

---

## Database state (21 March 2026)
- **DB file:** 1.7 GB (compacted from 7.7GB)
- **hourly_counts:** 73.4M rows (Jan 2024–Mar 2026, ~3,860 VIC stations)
- **speed_observations:** ~895K rows (Bluetooth, accumulating)
- **tirtl_counts:** 3.09M rows (Mar 2026, 406 sites)
- **fuel_prices:** 14,277 rows (2 snapshot dates: 18 Mar + 21 Mar)
- **wholesale_prices:** 840 rows (2023–present, pre-2023 pruned)
- **calendar:** 1,461 rows (2023–2026)
- **Metro core:** 967 stations (P75+ from Feb 2026 baseline, threshold ~46,272 daily vehicles)

---

## Scripts inventory

| Script | Purpose | Status |
|---|---|---|
| `create_schema.py` | Create DuckDB tables | ✅ |
| `ingest_vic_counts.py` | Load VIC SCATS counts (monthly) | ✅ |
| `ingest_vic_stations.py` | Load VIC SCATS sites (CRS reprojection) | ✅ |
| `ingest_tirtl.py` | Load TIRTL counts + sites | ✅ |
| `ingest_vic_transport.py` | Load PT patronage + fleet data | ✅ |
| `populate_calendar.py` | Populate date dimension | ✅ |
| `poll_bluetooth.py` | Continuous Bluetooth speed poller | ✅ Running |
| `poll_fuel_prices.py` | Servo Saver retail fuel snapshot | ✅ |
| `refresh_brent.py` | EIA Brent crude + RBA AUD/USD | ✅ |
| `ingest_wholesale_prices.py` | AIP TGP wholesale scrape | ✅ |
| `ingest_fuel_stations.py` | Servo Saver station reference | ✅ |
| `daily_refresh.py` | Orchestrates all daily fuel/price refreshes | ✅ New |
| `compact_db.py` | Export/reimport DB to reclaim WAL bloat | ✅ New |
| `weekly_refresh.py` | Fuel crisis weekly report | ✅ |

---

## Recent sessions

**21 March 2026 — Metro core, YoY, labelling, daily refresh, DB compaction**
- Added metro core station filter (P75+, ~967 stations) to Monitor, weekly trend, daily counts, month-on-month, school holiday effect
- Shared `create_metro_core_table()` helper in `api/db.py` for consistency
- Added YoY comparison line to weekly trend chart (faint, 25% opacity)
- YoY analysis: +1.3% overall — consistent with population growth, no behavioural change
- Updated all panel titles and added explanatory notes (what a station is, what a link is)
- Added Y-axis labels and descriptive tooltips across all charts
- Changed date format to Australian (dd MMM)
- Added weekday/Saturday/Sunday toggle to hourly profile chart
- Matched daily counts bar chart height to hourly profile (320px)
- Created `daily_refresh.py` — orchestrates retail fuel, Brent/FX, AIP wholesale refreshes
- Confirmed Servo Saver API key is working (OPEN-007 resolved)
- Compacted database: 7.7GB → 1.7GB via parquet export + CREATE TABLE AS reimport
- Pruned pre-2023 wholesale prices (4,957 rows) and calendar entries (1,096 rows)
- Restored PKs on speed_observations, bluetooth_routes, bluetooth_links; UNIQUE index on fuel_prices
- Cost analysis for hosting: VPS $6–10/month viable with compacted DB

**18 March 2026 — Fuel price pipeline**
- Integrated Servo Saver (retail), AIP TGP (wholesale), EIA Brent crude, RBA AUD/USD
- Built 4 scripts, 3 new DuckDB tables, 6 fuel API endpoints
- Dashboard fuel tab with state average, price chain, traffic overlay, postcode search

**15 March 2026 — Data pipeline + first charts + fuel crisis monitor**
- Full ingestion pipeline: 94.5M rows loaded
- First charts, weekly monitor, identified NSW sensor degradation

---

## Things to remember
- Phil wants to explore and discuss before code is written — ask first, build second
- **Metro core filter** is the standard for Monitor and Analysis — ~967 stations, P75+ from Feb 2026 baseline
- **Bluetooth poller** runs continuously — connect/disconnect per cycle to avoid DuckDB write lock conflicts
- **DuckDB concurrency:** stop Bluetooth poller before large ingestion jobs
- **Vite workaround:** always start from `/tmp/amip-frontend` symlink
- **DB compaction:** use parquet export + CREATE TABLE AS (not INSERT INTO) for large tables
- **Daily refresh:** `daily_refresh.py --loop` handles all fuel/price data at 7am AEST
- Project folder: `/Users/doug/Projects/Traffic Movement`

---

*Update this file at the end of every session.*
