# memory.md — Traffic Movement
> Persistent session notes. Updated at the end of every working session. Captures what was decided, what's in progress, and what needs resolving next.

---

## Last updated
16 March 2026 — 9-panel dashboard live. API + React frontend working. Both cities verified.

---

## Settled decisions
- DuckDB confirmed as data layer (DEC-001)
- React JSX confirmed as frontend (DEC-002)
- Australian cities as initial geographic scope (DEC-005)
- Modular architecture with 150 line soft limit (DEC-003)
- Three-layer documentation: inline JSDoc + module READMEs + RUNTIME.md (DEC-004)
- Data accuracy is non-negotiable — all values verified to source (DEC-006)
- Auth and payment treated as isolated modules from day one, solutions TBD
- **V1 cities: Sydney (NSW) + Melbourne (VIC) only** — QLD/WA/SA rejected, annual data only (DEC-007)
- **Unified DuckDB schema: 6 tables** — stations, hourly_counts, speed_observations, bluetooth_routes, calendar, data_modules (DEC-008)
- **Build priority: time-series charting first** (DEC-009)
- **Recharts for V1 charts** (DEC-010)
- **Local dev only for V1** — no cloud deployment yet (DEC-011)
- **Sydney reliable network: 26 stations** — only these used for year-on-year comparisons (DEC-012)
- **VIC SCATS: site-level hourly aggregation** — detectors summed, 15-min summed to hourly (DEC-013)
- **VIC coordinates: EPSG:3111 (VicGrid94)** — reprojected to WGS84 in ingestion (DEC-014)
- **Fuel crisis baseline: Feb 2026 weekday average** — used for weekly monitoring (DEC-015)
- Full decisions log in `decisions.md`

---

## Current blockers / open threads
- Need fresh SCATS data (w/c 16 March+) to detect fuel crisis traffic impact — only 4 post-crisis weekdays so far
- Dashboard is long (9 panels) — may need navigation/tabs for usability
- Vite requires `/tmp/amip-frontend` symlink due to space in project folder name
- TIRTL dataset (VIC, announced 9 March 2026) not yet available for download (OPEN-006)
- Auth approach not decided — deferred (OPEN-001)
- Payment provider not decided — deferred (OPEN-002)
- Hosting decision outstanding — deferred to post-V1 (OPEN-004)

---

## Key data findings (this session)

### Database state
- **94.5M rows** in hourly_counts (21.1M NSW + 73.4M VIC)
- **4,259 stations** (295 Sydney permanent + 3,964 Melbourne SCATS)
- **DB size:** 6.9 GB
- NSW: 2006–Feb 2026, VIC: Jan 2024–Mar 2026

### NSW sensor degradation
- Only 63 of 295 Sydney permanent stations reported in 2026 (was 200+ in 2010–2018)
- TfNSW has acknowledged the issue — service rebuild underway, no timeline
- **26 stations identified as reliable** for year-on-year comparison (DEC-012)
- Unreliable stations show false drops of 45–67% — these are sensor failures, not traffic changes

### Sydney traffic recovery (reliable network, 26 stations)
- 2025 peak: 822 vehicles/hr (weekday avg at 7am)
- 2019 pre-COVID peak: 896 vehicles/hr
- **Recovery: ~92% of pre-COVID levels** (-8.3%)
- 2021 lockdown trough was -15.4% — recovery has been steady
- Friday is the busiest weekday; Sunday the quietest

### Melbourne traffic patterns
- Hoddle St (Collingwood): consistent ~8,700 vehicles/hr at 4–5pm peak, stable 2024 vs 2025
- Eastern Freeway off-ramp: busiest site at 7,192/hr avg. Wed/Thu afternoons heaviest.
- SCATS network is healthy — ~3,860 stations reporting consistently across all 27 months

### Fuel crisis (Strait of Hormuz, ~3 March 2026)
- Iran retaliated against US-Israeli strikes, effectively closed Strait of Hormuz
- Government declared "national crisis", released 762M litres from reserves on 13 March
- Regional stations rationing fuel ($20 limits), prices above $2/litre
- Melbourne w/c 9 March: down 6.3% vs Feb baseline — BUT Labour Day (public holiday) explains most of it
- Individual weekdays 10–13 March appear normal (33,600–36,800 per station)
- **Too early to detect behavioural shift** — need w/c 16 March data (no holidays) to see a real signal

---

## Scripts inventory

| Script | Purpose | Status |
|---|---|---|
| `scripts/create_schema.py` | Create DuckDB tables | ✅ Working |
| `scripts/ingest_nsw_stations.py` | Load Sydney permanent stations | ✅ Working |
| `scripts/ingest_vic_stations.py` | Load VIC SCATS sites (with CRS reprojection) | ✅ Working |
| `scripts/ingest_nsw_counts.py` | Load NSW hourly counts (unpivot) | ✅ Working |
| `scripts/ingest_vic_counts.py` | Load VIC SCATS counts (aggregate + multi-month) | ✅ Working |
| `scripts/populate_calendar.py` | Populate date dimension (holidays, events) | ✅ Working |
| `scripts/inspect_data.py` | One-off data inspection report | ✅ Working |
| `scripts/weekly_refresh.py` | Weekly fuel crisis monitor | ✅ Working |

---

## Recent sessions

**15 March 2026 — Data pipeline build + first charts + fuel crisis monitor**
- Downloaded NSW hourly permanent (5 CSV files, ~1 GB) and VIC SCATS (27 monthly ZIPs, Jan 2024–Mar 2026)
- Downloaded NSW station reference and VIC Traffic Lights reference
- Built and ran full ingestion pipeline: 94.5M rows loaded into DuckDB
- Inspected data: confirmed column names, join rates, coordinate systems, null rates
- Identified NSW sensor degradation — established 26-station reliable network (DEC-012)
- Produced first charts: Sydney hourly profiles (5 years), Melbourne Hoddle St, Eastern Fwy heatmap
- Built weekly traffic monitor script for fuel crisis tracking
- Researched fuel crisis context (Strait of Hormuz, government response)
- Added DEC-012 through DEC-015 to decisions.md

**14 March 2026 — Data research and schema design**
- Researched all five target cities' open data portals
- Designed unified DuckDB schema, produced data audit document
- Updated all context files

**March 2026 — Planning setup**
- Defined project concept, audience, and geographic scope
- Confirmed tech stack, built all `_context/` files

---

## Things to remember
- Doug wants to explore and discuss before any code is written — ask first, build second
- No assumptions on auth — present options at build time
- Payment module must be architected as isolated from day one even before it's built
- Data sources go in `data.md` as they are confirmed and verified
- **Always use the reliable network filter (26 stations) for Sydney year-on-year comparisons** — never show raw comparisons without filtering for sensor reliability
- **Fuel crisis is an active tracking interest** — weekly monitor is the tool, needs fresh SCATS data each week
- Project folder is `/Users/doug/Projects/Traffic Movement`
- AMIP project plan and prompt spec docs are in the Claude project files for reference
- Doug has TfNSW and VIC portal accounts registered

---

## Next session priorities
1. Download latest SCATS monthly ZIP (March 2026 should have more days by next week)
2. Run `ingest_vic_counts.py` + `weekly_refresh.py` to check for fuel crisis signal
3. Build FastAPI endpoint for DuckDB queries
4. Scaffold React app, build first Recharts component with real data
5. Check if TIRTL dataset has become available (OPEN-006)

---

*Update this file at the end of every session.*
