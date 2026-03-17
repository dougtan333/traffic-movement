# stage.md — Traffic Movement
> Current project phase and immediate priorities. Update this at the start of each new phase.

---

## Current stage

**Dashboard build complete — 5-tab dashboard with traffic counts, speed, PT patronage, and fleet data. Victoria-only focus.**

Last updated: 16 March 2026

---

## What this stage is about

Full-stack local dashboard built and running. Data pipeline covers road traffic (SCATS counts), real-time speed (Bluetooth polling), public transport patronage, and vehicle fleet composition. Frontend has 5 navigable tabs with 12 components rendering real Victorian transport data. Bluetooth poller running in background building a speed archive.

---

## What's done

### Foundation
- [x] Project concept, audience, geographic scope, build principles defined
- [x] Tech stack confirmed: React JSX, DuckDB, FastAPI, Recharts, Leaflet
- [x] All `_context/` files written and maintained
- [x] Git repo live: github.com/dougtan333/traffic-movement (7 commits)

### Data sources assessed
- [x] All five Australian capital cities assessed for open traffic data
- [x] NSW (TfNSW hourly counts) + VIC (SCATS, Bluetooth, PT patronage, fleet) confirmed
- [x] QLD, WA, SA ruled out — annual data only, no hourly granularity
- [x] Victoria-only focus confirmed for new data sources (DEC-016)

### Data pipeline
- [x] DuckDB schema: 9 tables (stations, hourly_counts, speed_observations, bluetooth_routes, pt_patronage_monthly, pt_patronage_daytype, vehicle_registrations, calendar, data_modules)
- [x] NSW hourly counts: 21.1M rows (2006–Feb 2026, 295 stations, 26 reliable)
- [x] VIC SCATS counts: 73.4M rows (Jan 2024–Mar 2026, ~3,860 stations)
- [x] VIC Bluetooth speed: polling live, 4,711 links per 5-min interval, accumulating
- [x] VIC PT patronage monthly: 95 rows (Jan 2018–Nov 2025, 6 modes)
- [x] VIC PT patronage by day type: 4,300 rows (weekday/school-hol/weekend × mode × day-of-week)
- [x] VIC vehicle registrations: 5.94M vehicles by fuel type (Q4 2025 snapshot)
- [x] Calendar: 2020–2026 with public holidays, school terms, major events
- [x] Weekly fuel crisis monitor script

### API (FastAPI, 14 endpoints)
- [x] Traffic: hourly-profile, hourly-profile-multi, weekly-trend, daily-counts, day-of-week, heatmap, station-profile, month-on-month, school-holiday-effect
- [x] Speed: snapshot, trend
- [x] Transport: pt-monthly, pt-daytype, fleet
- [x] Stations, monitor, health

### Frontend (React + Vite + Recharts, 5 tabs, 12 components)
- [x] **Monitor tab:** Metric cards, weekly trend, daily bars, speed panel (Melbourne only)
- [x] **Patterns tab:** Hour × day-of-week heatmap, hourly profile (multi-year), day-of-week bars
- [x] **Transport tab:** PT patronage stacked area chart, vehicle fleet fuel-type breakdown
- [x] **Explorer tab:** Leaflet station map (~3,860 MEL / 26 SYD), click-to-profile drilldown
- [x] **Analysis tab:** Month-on-month comparison table, school holiday effect
- [x] City toggle (Sydney/Melbourne) on all tabs
- [x] Design: DM Sans typography, editorial palette, tab navigation

### Key findings from data
- [x] NSW sensor network degrading — only 26 of 295 stations reliable across years (DEC-012)
- [x] Sydney traffic at ~92% of pre-COVID levels (2025 vs 2019, reliable network)
- [x] Melbourne SCATS network healthy — ~3,860 stations consistent across 27 months
- [x] Melbourne fuel crisis: w/c 9 Mar 2026 down 6.3% vs Feb baseline (but Labour Day confounds)
- [x] VIC school holiday effect: -8.6% traffic drop, December -22.9%
- [x] VIC fleet: 67.6% petrol, 27.3% diesel, 1.7% electric (Q4 2025)
- [x] VIC PT patronage recovered to ~42M trips/month (pre-COVID was ~60M)

---

## Immediate next steps

1. **Servo Saver fuel price API** — awaiting API key. Once received: build polling script, DuckDB table, price-vs-traffic overlay on Monitor tab
2. **Fresh SCATS data** — download latest March 2026 for first clean post-crisis week (w/c 16 Mar, no holidays)
3. **Speed trend chart** — Bluetooth poller accumulating history, chart auto-renders
4. **Deployment planning** — get it on a public URL (OPEN-004)
5. **Bicycle data** — 69MB zip downloaded but not ingested (dataset discontinued at 2024, lower priority)

---

## Running services

| Service | How to start | Port |
|---|---|---|
| FastAPI | `cd "/Users/doug/Projects/Traffic Movement" && python3 -m uvicorn api.main:app --port 8000` | 8000 |
| Vite | `cd /tmp/amip-frontend && NODE_ENV=development npx vite --port 5173` | 5173 |
| Bluetooth poller | `cd "/Users/doug/Projects/Traffic Movement" && PYTHONUNBUFFERED=1 nohup python3 scripts/poll_bluetooth.py --loop > logs/bluetooth_poller.log 2>&1 &` | — |
| caffeinate | `caffeinate -d &` (prevents Mac sleep while poller runs) | — |

Vite requires the `/tmp/amip-frontend` symlink due to space in project folder name.

---

## Weekly refresh workflow

1. Download latest SCATS monthly ZIP from https://opendata.transport.vic.gov.au/dataset/traffic-signal-volume-data
2. Extract to project folder (alongside existing monthly folders)
3. `python3 scripts/ingest_vic_counts.py`
4. `python3 scripts/weekly_refresh.py`

Reports saved to `reports/weekly_monitor_YYYY-MM-DD.json`.

---

## How Claude should behave at this stage

- **Dashboard is live** with 5 tabs, 12 components. Don't rebuild existing components unless asked.
- **Data pipeline is done** — ingestion scripts exist and work. Don't rebuild unless asked.
- **Victoria-only focus** for new data. NSW data retained but no new NSW sources.
- **Reliable network filter** for Sydney: always applied (DEC-012, 26 stations).
- **Bluetooth poller** is running — speed data accumulating in `speed_observations`.
- **Vite workaround**: always start from `/tmp/amip-frontend` symlink.
- **Ask before building** — confirm approach before creating new files or modules.
- **Fuel crisis** is an active area of interest — needs fresh SCATS data to detect behavioural shift.

---

## What the next stage looks like

**Stage 5: Productise**
- Deployment to a public URL (Cloudflare Pages + Railway/Render)
- Auth layer for extended access (OPEN-001)
- Automated data refresh (SCATS monthly, PT patronage, Bluetooth continuous)
- Additional VIC data: TIRTL (counts + speed + classification), VISTA travel survey
- Payment integration for premium features (OPEN-002)
