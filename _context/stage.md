# stage.md — Traffic Movement
> Current project phase and immediate priorities. Update this at the start of each new phase.

---

## Current stage

**Dashboard live with metro core filtering, YoY comparison, daily automated data refresh, and compacted database. Victoria-only.**

Last updated: 21 March 2026

---

## What this stage is about

Full-stack local dashboard with 6 navigable tabs, ~16 components. Data pipeline covers road traffic (SCATS counts filtered to metro core P75+ stations), real-time speed (Bluetooth polling), public transport patronage, vehicle fleet composition, and fuel prices (retail, wholesale, international crude). Daily refresh script automates all fuel/price data updates. Database compacted from 7.7GB to 1.7GB via parquet export/reimport — viable for VPS hosting.

---

## What's done

### Foundation
- [x] Project concept, audience, geographic scope, build principles defined
- [x] Tech stack confirmed: React JSX, DuckDB, FastAPI, Recharts, Leaflet
- [x] All `_context/` files written and maintained
- [x] Git repo live: github.com/dougtan333/traffic-movement

### Data pipeline
- [x] DuckDB schema: 15 tables across traffic, speed, fuel, PT, fleet
- [x] VIC SCATS counts: 73.4M rows (Jan 2024–Mar 2026, ~3,860 stations)
- [x] VIC Bluetooth speed: polling live, 4,711 links per 5-min interval
- [x] VIC retail fuel prices: daily snapshots via Servo Saver API
- [x] Wholesale prices: AIP TGP + EIA Brent crude + RBA AUD/USD
- [x] PT patronage, vehicle registrations, TIRTL counts, calendar
- [x] NSW data retained in DB but not displayed (DEC-019)

### Metro core filtering (DEC-020)
- [x] P75+ station threshold from Feb 2026 baseline = ~967 stations
- [x] Shared helper `create_metro_core_table()` in `api/db.py`
- [x] Applied to: Monitor (metric cards + weekly trend + daily counts), Analysis (month-on-month + school holiday effect)
- [x] Full network (~3,860 stations) still used for Patterns tab

### YoY comparison
- [x] Weekly trend chart includes prior-year line (faint, 25% opacity)
- [x] API `/api/traffic/weekly-trend` returns `yoy_data` array
- [x] Tooltip shows both current and prior year values on hover

### Labelling and UX
- [x] All panel titles describe what the metric is (e.g. "Weekly traffic — metro core stations (top 25% by volume)")
- [x] Panel notes explain what a station is and what a Bluetooth link is
- [x] Y-axis labels and tooltips show units (vehicles/day/station, vehicles/15 min/station, etc.)
- [x] Date format changed to Australian (dd MMM, e.g. "9 Mar")
- [x] Hourly profile chart has weekday/Saturday/Sunday toggle

### Daily automated refresh
- [x] `scripts/daily_refresh.py` — runs retail fuel, Brent/FX, AIP wholesale
- [x] Start with `--loop` for 7am AEST daily execution
- [x] Servo Saver API key confirmed working (OPEN-007 resolved)

### Database compaction
- [x] Exported all tables to parquet (446MB actual data)
- [x] Rebuilt fresh DB from parquet via CREATE TABLE AS
- [x] DB reduced from 7.7GB → 1.7GB (78% reduction)
- [x] Pre-2023 wholesale prices and calendar entries pruned
- [x] PKs restored on speed_observations, bluetooth_routes, bluetooth_links
- [x] UNIQUE index on fuel_prices for INSERT OR IGNORE support

### API (FastAPI, 20+ endpoints)
- [x] Traffic: hourly-profile, hourly-profile-multi (with day_type param), weekly-trend (with YoY), daily-counts, day-of-week, heatmap, station-profile, month-on-month, school-holiday-effect
- [x] Speed: snapshot, trend, roads
- [x] Transport: pt-monthly, pt-daytype, fleet
- [x] Fuel: state-average, by-postcode, postcodes, heatmap, price-chain, traffic-overlay
- [x] Stations, monitor (metro core), calendar-events, health

### Frontend (React + Vite + Recharts, 6 tabs, ~16 components)
- [x] **Monitor tab:** Metric cards (metro core), weekly trend (with YoY line), daily bars (metro core), speed panel (Bluetooth)
- [x] **Patterns tab:** Hour × day-of-week heatmap, hourly profile (multi-year, weekday/Sat/Sun toggle), day-of-week bars
- [x] **Fuel tab:** State average, oil-to-pump price chain, traffic vs fuel overlay, cheapest fuel by postcode
- [x] **Transport tab:** PT patronage stacked area, vehicle mix (TIRTL), speed profile, fleet fuel-type breakdown, daily patronage by day type
- [x] **Explorer tab:** Leaflet station map, click-to-profile drilldown
- [x] **Analysis tab:** Month-on-month (metro core), school holiday effect (metro core)

---

## Immediate next steps

1. **Fresh SCATS data** — download latest from VIC portal for clean post-crisis analysis
2. **Deployment planning** — VPS ($6–10/month) for API + DB + pollers; Cloudflare Pages for frontend (OPEN-004)
3. **Postcode history chart** — needs accumulated daily fuel snapshots before meaningful
4. **Speed trend visualisation** — Bluetooth archive growing, chart auto-renders

---

## Running services

| Service | How to start | Port |
|---|---|---|
| FastAPI | `cd "/Users/doug/Projects/Traffic Movement" && PYTHONUNBUFFERED=1 nohup python3 -m uvicorn api.main:app --port 8000 > logs/api.log 2>&1 &` | 8000 |
| Vite | `cd /tmp/amip-frontend && NODE_ENV=development npx vite --port 5173` | 5173 |
| Bluetooth poller | `cd "/Users/doug/Projects/Traffic Movement" && PYTHONUNBUFFERED=1 nohup python3 scripts/poll_bluetooth.py --loop > logs/bluetooth.log 2>&1 &` | — |
| Daily refresh | `cd "/Users/doug/Projects/Traffic Movement" && PYTHONUNBUFFERED=1 nohup python3 scripts/daily_refresh.py --loop > logs/daily_refresh.log 2>&1 &` | — |

Vite requires the `/tmp/amip-frontend` symlink due to space in project folder name.

---

## Data refresh cadence

| Source | Script | Frequency |
|---|---|---|
| Retail fuel (Servo Saver) | `daily_refresh.py` | Daily (automated, 7am AEST) |
| Brent crude (EIA) | `daily_refresh.py` | Daily (automated) |
| AUD/USD (RBA) | `daily_refresh.py` | Daily (automated) |
| AIP Terminal Gate | `daily_refresh.py` | Daily (automated, may timeout) |
| SCATS vehicle counts | `ingest_vic_counts.py` | Monthly (manual download) |
| Bluetooth speed | `poll_bluetooth.py` | Continuous (every 5 min) |
| TIRTL | `ingest_tirtl.py` | As released (manual) |
| Fuel stations | `ingest_fuel_stations.py` | Monthly (manual) |
| Calendar/events | `populate_calendar.py` | As needed |
| PT/Fleet data | `ingest_vic_transport.py` | Annual |

---

## How Claude should behave at this stage

- **Dashboard is live** with 6 tabs, ~16 components. Don't rebuild existing components unless asked.
- **Metro core filter** (P75+ stations, ~967) is used on Monitor, daily counts, and Analysis tabs. Patterns tab uses full network.
- **Victoria-only focus.** NSW data retained but not queried or displayed.
- **Bluetooth poller** is running — speed data accumulating in speed_observations.
- **Daily refresh** handles all fuel/price data automatically.
- **Vite workaround:** always start from `/tmp/amip-frontend` symlink.
- **Ask before building** — confirm approach before creating new files or modules.
- **DB is compacted** — 1.7GB. Old 7.7GB file and parquet export still on disk (not yet deleted).

---

## What the next stage looks like

**Stage 5: Productise**
- Deployment to a public URL (VPS for API/DB/pollers + Cloudflare Pages for frontend)
- Auth layer (OPEN-001)
- Automated SCATS monthly ingestion
- Payment integration (OPEN-002)
