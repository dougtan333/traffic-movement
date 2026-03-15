# stage.md — Traffic Movement
> Current project phase and immediate priorities. Update this at the start of each new phase.

---

## Current stage

**Dashboard build — 9-panel interactive dashboard live with real data.**

Last updated: 16 March 2026

---

## What this stage is about

Data pipeline is built and loaded (94M+ rows). First visualisations have been produced from real data — hourly profiles, day-of-week patterns, year-on-year comparisons. A weekly traffic monitor script tracks the ongoing Australian fuel crisis. The project is ready to move into frontend build.

---

## What's done

- [x] Project concept defined
- [x] Audience identified
- [x] Geographic scope set (Australian cities)
- [x] Core product principles established
- [x] Tech stack confirmed (React JSX + DuckDB)
- [x] All `_context/` files written and wired
- [x] Data source research — all five target cities assessed
- [x] V1 data sources confirmed: NSW (TfNSW hourly counts) + VIC (SCATS counts, Bluetooth speed)
- [x] QLD, WA, SA ruled out for V1 (annual data only, no hourly)
- [x] Unified DuckDB schema designed and created (6 tables)
- [x] Data audit document produced (amip_data_audit.docx)
- [x] Key data gap identified: NSW has no public speed data — Sydney is count-only in V1
- [x] Registered for TfNSW and VIC portal accounts
- [x] Downloaded and inspected NSW hourly permanent data — confirmed column names match schema
- [x] Downloaded and inspected VIC SCATS data — confirmed format
- [x] VIC Traffic Lights reference downloaded — CRS confirmed as EPSG:3111 (VicGrid94)
- [x] NSW station reference loaded: 295 Sydney permanent stations
- [x] VIC station reference loaded: 3,964 SCATS-matched signal sites (with CRS reprojection)
- [x] NSW hourly counts loaded: 21.1M rows (2006–Feb 2026, 295 stations)
- [x] VIC hourly counts loaded: 73.4M rows (Jan 2024–Mar 2026, 27 months, ~3,860 stations)
- [x] Calendar populated: 2020–2026 with public holidays, school terms, major events
- [x] TIRTL dataset not yet available for download — not a blocker
- [x] FastAPI server built — 8 endpoints serving real data from DuckDB
- [x] React frontend scaffolded (Vite + Recharts)
- [x] Dashboard live with 9 panels: metric cards, weekly trend, daily bar chart, heatmap, station map + drilldown, month-on-month table, hourly profile, day-of-week, school holiday effect
- [x] City toggle (Sydney/Melbourne) switches all panels
- [x] Station explorer: Leaflet map with ~3,860 Melbourne / 26 Sydney clickable stations, profile card on click
- [x] Vite space-in-path workaround documented (symlink to /tmp/amip-frontend)
- [x] First chart: Sydney reliable network hourly profile (2019 vs 2020 vs 2021 vs 2024 vs 2025)
- [x] Identified NSW sensor degradation issue — only 26 of 295 stations have reliable data across years
- [x] Established "reliable network" filter: 26 Sydney stations with consistent data 2019–2025
- [x] Melbourne Hoddle St hourly profile — verified SCATS data consistency (2024 vs 2025)
- [x] Melbourne Eastern Freeway heatmap — day-of-week × hour-of-day traffic patterns
- [x] Weekly traffic monitor script (`weekly_refresh.py`) — compares latest week vs Feb 2026 baseline, vs prior week, vs same week last year
- [x] First monitor report generated: Melbourne w/c 9 Mar 2026 down 6.3% vs baseline (Labour Day effect)
- [x] Fuel crisis context researched: Strait of Hormuz closure ~3 Mar 2026, government releasing reserves 13 Mar

---

## Immediate next steps

1. Download latest SCATS data as March 2026 progresses — need post-crisis weekdays (w/c 16 Mar+) to detect behavioural shift
2. Design improvements — typography, spacing, responsive polish
3. Add navigation/tabs to organise panels (dashboard is long — consider sections or tabs)
4. Additional views: corridor comparison, event overlay (AFL GF, Melbourne Cup), public holiday annotations on all charts
5. VIC Bluetooth API polling for speed data
6. Plan API-based data refresh (TfNSW CKAN API for incremental NSW updates)

---

## Weekly refresh workflow

To monitor the fuel crisis impact on traffic:

1. Download latest SCATS monthly ZIP from https://opendata.transport.vic.gov.au/dataset/traffic-signal-volume-data
2. Extract to project folder (alongside existing monthly folders)
3. Run: `python scripts/ingest_vic_counts.py`
4. Run: `python scripts/weekly_refresh.py`

Reports are saved to `reports/weekly_monitor_YYYY-MM-DD.json`.

---

## How Claude should behave at this stage

- **Dashboard is live** — 9 panels rendering real data. Don't rebuild existing components unless asked.
- Data pipeline is **done** — ingestion scripts exist and work. Don't rebuild unless asked.
- Schema is **populated** — 94M+ rows in hourly_counts. Query it directly.
- **Reliable network filter** for Sydney: always applied (DEC-012). Never show raw year-on-year comparisons without filtering.
- The **fuel crisis** is an active area of interest — weekly monitor is set up, needs fresh data.
- **Vite workaround**: always start from `/tmp/amip-frontend` symlink, not the project folder directly.
- Ask before creating new files or modules — confirm approach first.

---

## What the next stage looks like

**Stage 4: Polish and extend**
- UI/UX refinement — navigation, responsiveness, design polish
- Event annotation overlays (AFL GF, Melbourne Cup, public holidays) on all relevant charts
- Corridor comparison view — compare two specific roads side by side
- VIC Bluetooth polling for speed/congestion data
- Deployment planning (OPEN-004)

---
