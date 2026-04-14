# decisions.md — Traffic Movement
> Architecture and product decisions log. Every significant choice is recorded here with its rationale. Once logged, decisions are not revisited without a new entry explaining why.

---

## How to use this file

When a decision is made — in conversation, in planning, or mid-build — add an entry here immediately. Include what was decided, why, and what was ruled out. This stops Claude (and future collaborators) from re-opening settled questions or suggesting approaches already considered and rejected.

---

## Confirmed decisions

### DEC-001 — Data layer: DuckDB
**Decision:** DuckDB is the default and preferred data layer for all querying and processing.
**Rationale:** Performant for analytical queries on local or file-based datasets, well-suited to the kinds of aggregations and historical comparisons this project requires. Avoids the overhead of a server-based database for a data-exploration product.
**Ruled out:** Server-based databases (Postgres, MySQL) — unnecessary infrastructure for this use case at this stage.
**Status:** Confirmed ✅

---

### DEC-002 — Frontend: React JSX
**Decision:** Frontend is built in React JSX.
**Rationale:** Component-based architecture aligns with the modular build requirement. Strong ecosystem for data visualisation libraries.
**Status:** Confirmed ✅

---

### DEC-003 — Architecture: Modular, single-responsibility
**Decision:** All code is modular. Every file has one responsibility. 150 line soft limit per file.
**Rationale:** Makes the codebase maintainable, testable, and extensible as data sources and features grow. Also supports future contributors and Claude sessions picking up work cleanly.
**Status:** Confirmed ✅

---

### DEC-004 — Documentation: Inline JSDoc + README per module + RUNTIME.md
**Decision:** Three-layer documentation — inline JSDoc comments, a README per module, and a project-level RUNTIME.md for operational process.
**Rationale:** Inline comments serve developers during build. Module READMEs serve anyone navigating the codebase. RUNTIME.md serves anyone running or maintaining the live application.
**Status:** Confirmed ✅

---

### DEC-005 — Geographic scope: Australian cities first
**Decision:** Initial scope is Australian cities. Architecture must support expansion without structural changes.
**Rationale:** Scopes the data problem to manageable size while keeping growth path open. Australian government open data is reasonably accessible.
**Status:** Confirmed ✅

---

### DEC-006 — Data accuracy: Source-verified only
**Decision:** No data values are presented without being verified back to the original source. Derived or approximated values are flagged explicitly.
**Rationale:** Core to the product's credibility. Users — including researchers and planners — are trusting the data. Errors erode that trust permanently.
**Status:** Confirmed ✅

---

### DEC-007 — V1 data sources: NSW + VIC only
**Decision:** V1 uses real data from two cities only — Sydney (NSW) and Melbourne (VIC). Queensland, Western Australia, and South Australia are excluded from V1.
**Rationale:** NSW and VIC are the only Australian states providing publicly accessible hourly or sub-hourly traffic count data. QLD, WA, and SA only publish annual average daily traffic (AADT) — no hourly granularity, which doesn't support time-series charting. Starting with real data from the outset rather than synthetic data.
**Ruled out:** Synthetic/sample data approach — user preference to work with real datasets from the start. All five cities at launch — data quality insufficient for QLD/WA/SA.
**Data sources confirmed:** TfNSW hourly permanent counts (SRC-001), VIC SCATS signal volumes (SRC-002), VIC Bluetooth travel time (SRC-007). See `data.md` for full details.
**Status:** Confirmed ✅

---

### DEC-008 — Unified DuckDB schema: four tables
**Decision:** All traffic data normalised into four DuckDB tables: `stations` (unified site reference), `hourly_counts` (core fact table — one row per station per hour), `speed_observations` (VIC Bluetooth speed/travel time), `calendar` (date dimension with holidays and events).
**Rationale:** NSW and VIC use different source systems and granularities (NSW hourly, VIC 15-min). A unified schema allows cross-city queries and charting from a single data model. VIC 15-min data is aggregated to hourly to match NSW. Speed data is separate because only VIC provides it in V1.
**Ruled out:** Keeping raw source schemas — would require city-specific query logic in every chart component, violating the modular architecture principle.
**Status:** Confirmed ✅

---

### DEC-009 — V1 build priority: time-series traffic charting first
**Decision:** First working build focuses on time-series traffic charting (vehicle speed and counts over time), followed by dashboard with metric cards, then historical comparison, then mobility trends.
**Rationale:** Time-series charting is the most data-rich use case and exercises the full pipeline (ingest → DuckDB → API → chart). Gets a working end-to-end system fastest.
**Status:** Confirmed ✅

---

### DEC-010 — Chart library: Recharts
**Decision:** Recharts for V1 chart rendering.
**Rationale:** Already available in the React ecosystem, well-suited to line charts, bar charts, and area charts needed for time-series traffic data. Can reassess for heatmaps or more complex viz later (D3, Plotly as options).
**Status:** Confirmed ✅

---

### DEC-011 — V1 deployment: local dev only
**Decision:** V1 is local development only. No cloud deployment for first build.
**Rationale:** Focus on getting the data pipeline and charting working correctly before introducing deployment complexity. Hosting decision (OPEN-004) deferred to post-V1.
**Status:** Confirmed ✅

---

### DEC-012 — Sydney reliable network filter
**Decision:** Year-on-year and cross-period comparisons for Sydney must use the "reliable network" — a curated set of 26 stations with consistent data coverage from 2019 to 2025 (≥200 weekdays reported per year, plausible volume change between -20% and +25%).
**Rationale:** NSW sensor network is degrading — only 63 of 295 permanent stations reported data in 2026, down from 200+ in 2010–2018. Comparing raw station averages across years produces misleading results (e.g. Military Road Mosman showed a -59% drop that was sensor failure, not a traffic decline). The 26-station reliable set was identified by requiring ≥200 weekday reporting days in both 2019 and 2025, with avg volume ≥400/hr, and change within a plausible range.
**Ruled out:** Using all 295 stations for historical comparisons — produces inaccurate results due to sensor dropout. Using only the most recent year's active stations — loses the ability to compare against pre-COVID baseline.
**Station IDs:** NSW_56841, NSW_58870, NSW_57051, NSW_15828001, NSW_15370001, NSW_57104, NSW_57096, NSW_15648001, NSW_57368, NSW_15154104, NSW_99990010, NSW_15334016, NSW_15252028, NSW_15286008, NSW_15334001, NSW_57140, NSW_15286003, NSW_15828005, NSW_15286009, NSW_15286011, NSW_57268, NSW_57440, NSW_57439, NSW_15252035, NSW_99990003, NSW_15286013
**Status:** Confirmed ✅

---

### DEC-013 — VIC SCATS aggregation: site-level hourly
**Decision:** VIC SCATS 15-minute detector-level data is aggregated to site-level hourly totals during ingestion. Individual detector readings are not stored.
**Rationale:** 61% of raw SCATS rows are zero-volume (inactive detectors). Storing per-detector data would add noise and bloat. Summing across detectors per site gives the total intersection throughput, which is the meaningful metric for traffic monitoring. Aggregating to hourly matches the NSW schema for cross-city queries.
**Status:** Confirmed ✅

---

### DEC-014 — VIC coordinate system: EPSG:3111 (VicGrid94)
**Decision:** VIC Traffic Lights reference coordinates are in EPSG:3111 (VicGrid94), not MGA Zone 55. Reprojection to WGS84 (EPSG:4326) is handled in `ingest_vic_stations.py` using pyproj.
**Rationale:** Confirmed by reprojection testing — MGA55 produced coordinates in Antarctica; VicGrid94 correctly placed all samples in Victorian locations.
**Status:** Confirmed ✅

---

### DEC-015 — Fuel crisis baseline: February 2026 weekday average
**Decision:** For tracking the impact of the March 2026 fuel crisis on traffic, the baseline is February 2026 weekday average per station. Comparisons are also made against the same week from the prior year.
**Rationale:** Feb 2026 is the most recent full month before the crisis onset (~3 March). It had no public holidays that would distort the average (Australia Day is 26 Jan). Using per-station averages normalises for any network changes.
**Status:** Confirmed ✅

---

### DEC-016 — Victoria-only focus for new data sources
**Decision:** All new data sources from this point forward are Victorian only. NSW data already ingested (SCATS counts, 26-station reliable network) is retained, but no new NSW datasets will be added.
**Rationale:** VIC open data is consistently more comprehensive, better documented, and more granular than NSW equivalents. NSW traffic sensor network is degrading (only 26 reliable stations from 295). VIC provides PT patronage, vehicle registrations, cycling data, Bluetooth speed, and TIRTL — NSW has no comparable open datasets for most of these. Focusing on one state deeply produces a better product than covering two states thinly.
**Ruled out:** Continuing to add NSW data sources — quality gap too large, effort better spent on VIC depth.
**Status:** Confirmed ✅

---

## Open decisions

### OPEN-001 — Authentication approach
**Question:** What auth solution to use for the extended access tier?
**Options to assess at build time:** Supabase Auth, Auth0, Clerk, NextAuth, custom JWT
**Dependencies:** Depends on hosting choice and whether a backend is introduced
**Trigger:** Assess when extended access tier scope is defined
**Status:** Open ⬜

---

### OPEN-002 — Payment integration
**Question:** What payment provider and model for extended access?
**Options:** Stripe (most likely), Paddle, Lemon Squeezy
**Dependencies:** Depends on what extended access actually includes (features TBD)
**Trigger:** Assess when monetisation scope is defined
**Note:** Payment module must be fully isolated from day one regardless of when it's built
**Status:** Open ⬜

---

### OPEN-004 — Hosting and deployment
**Question:** Where does this application run?
**Options:** Vercel, Netlify, Fly.io, AWS, self-hosted
**Dependencies:** DuckDB file access patterns, data size, expected traffic
**Trigger:** Post-V1, once local dev version is working
**Status:** Open ⬜

---

### OPEN-005 — Historical data storage
**Question:** How is historical data stored and versioned?
**Considerations:** File-based (Parquet via DuckDB), database snapshots, API with date parameters
**Dependencies:** Partially resolved — raw CSV files kept as extracted directories in project root, DuckDB database is the queryable store. Remaining question is whether to convert to Parquet for long-term archive efficiency.
**Trigger:** When database exceeds ~10 GB or when deployment strategy is decided
**Status:** Partially resolved — working approach in place, optimisation deferred

---

### OPEN-006 — TIRTL dataset viability
**Question:** Does the newly released VIC TIRTL dataset provide historical speed + count data in a usable format?
**Resolution:** Yes. Downloaded and ingested 12 March 2026 release. 406 sites, 3.09M aggregated rows (1–13 March 2026), 15-min intervals with vehicle classification (Austroads 14 classes) and speed bins. Now integrated into the dashboard on the Transport tab.
**Status:** Resolved ✅

---

### OPEN-007 — Servo Saver fuel price API access
**Question:** Can we access the Victorian fuel price API to correlate prices with traffic patterns?
**Resolution:** Yes. API access approved. Full integration completed 18 March 2026. Three fuel data sources integrated: Servo Saver (retail), AIP TGP (wholesale), EIA+RBA (Brent crude + AUD/USD).
**Status:** Resolved ✅

---

### DEC-017 — Fuel price data: three-layer architecture
**Decision:** Fuel price data uses three sources forming the oil-to-pump price chain: (1) EIA API for daily Brent crude spot price (USD/barrel), (2) AIP TGP for daily Melbourne wholesale price (cents/litre), (3) Servo Saver API for daily VIC retail station-level prices. RBA provides AUD/USD exchange rate for Brent conversion.
**Rationale:** The ACCC methodology shows a ~10–14 day lag from international benchmark to Australian pump. Showing all three layers lets users see price shocks coming before they hit the pump. Each source is free and automatable: EIA via REST API, AIP via Excel seed + HTML scrape, Servo Saver via REST API with daily polling.
**Lag model (ACCC standard):** Singapore Mogas 95 lagged 10 days = approximate retail price. We approximate using Brent crude (available free) since Mogas 95 is proprietary (Argus/Platts). AIP TGP lagged 7 days tracks retail closely.
**Ruled out:** FuelPrice.io (commercial, terms may limit use), GlobalPetrolPrices (CC-NC-ND, weekly only), direct Mogas 95 data (proprietary, no free API).
**DuckDB tables:** `fuel_stations` (1,678 rows), `fuel_prices` (daily snapshots), `wholesale_prices` (5,795 rows — TGP + Brent + AUD/USD).
**Scripts:** `ingest_fuel_stations.py`, `poll_fuel_prices.py`, `ingest_wholesale_prices.py`, `refresh_brent.py`.
**Status:** Confirmed ✅

---

### DEC-018 — Servo Saver 9999.9 sentinel price handling
**Decision:** Fuel prices of 9999.9 c/l are treated as sentinel/placeholder values and filtered out of all aggregations and display. Stations reporting 9999.9 are included in station counts but excluded from price calculations.
**Rationale:** First API poll (18 March 2026) showed several stations with 9999.9 c/l — clearly not a real price. Likely means "not yet set" or "system default". Including them would skew averages.
**Filter:** `WHERE price_cpl > 0 AND price_cpl < 500` in all price queries.
**Status:** Confirmed ✅

---

### DEC-019 — Remove all Sydney/NSW data from dashboard
**Decision:** All Sydney/NSW references removed from API endpoints, frontend components, and constants. Dashboard is Victoria-only. NSW data retained in DuckDB (21.1M rows) but not queried or displayed.
**Rationale:** NSW sensor network is degrading (only 26 of 295 stations reliable), data quality differs substantially from VIC. Maintaining dual-city logic adds complexity for little value. VIC has 10+ data sources (SCATS, Bluetooth, TIRTL, PT, fleet, fuel prices); NSW has one (counts only). Cleaner product with single-state focus.
**What was removed:** CitySelector component, city state in App.jsx, city query parameter from all API endpoints, `api/constants.py` (reliable network IDs), Sydney colour from CSS/constants, city-conditional rendering in SpeedPanel/StationMap/HourlyProfileChart.
**What was retained:** NSW data in DuckDB (not deleted — available for future use if needed), NSW ingestion scripts (not deleted — dormant).
**Status:** Confirmed ✅

### DEC-020 — Metro core station filter (top 25% by volume)
**Decision:** Monitor, weekly trend, daily counts, and Analysis tab endpoints filter to "metro core" stations — the top 25% (P75+) by average daily volume from the Feb 2026 baseline period. This yields ~967 stations out of ~3,860.
**Rationale:** Averaging across all stations (including quiet suburban intersections) dilutes the signal. A 5% drop at a station doing 40,000 vehicles/day is meaningful; at one doing 2,000/day it's noise. The P75 threshold (~46,272 daily vehicles) captures Melbourne's busy inner-urban arterials and freeway intersections where week-on-week changes are significant.
**Implementation:** Shared helper `create_metro_core_table()` in `api/db.py` creates a temp table per request. Used by `/api/monitor/`, `/api/traffic/weekly-trend`, `/api/traffic/daily-counts`, `/api/traffic/month-on-month`, `/api/traffic/school-holiday-effect`.
**Ruled out:** Full network (~3,860 stations) — too much suburban noise. Top 10% (~400 stations) — considered too narrow for a robust average.
**Status:** Confirmed ✅

---

### DEC-021 — Database compaction via parquet export/reimport
**Decision:** When DuckDB file bloats from continuous Bluetooth poller writes, compact by exporting all tables to parquet (`EXPORT DATABASE ... FORMAT PARQUET`), creating a fresh DB, and loading via `CREATE TABLE AS SELECT * FROM read_parquet(...)`. Do NOT use `INSERT INTO` for large tables — DuckDB runs out of memory.
**Rationale:** DuckDB's VACUUM does not effectively reclaim space from WAL-heavy workloads. The Bluetooth poller writes 4,711 rows every 5 minutes, and over time the WAL bloat grew the DB from ~800MB actual data to 7.7GB. Parquet export + reimport is the reliable compaction method.
**Key learning:** `CREATE TABLE AS` works where `INSERT INTO` fails for large tables (73M rows) — it uses less memory.
**Status:** Confirmed ✅

---

### DEC-022 — Daily automated refresh script
**Decision:** `scripts/daily_refresh.py` orchestrates all daily data refreshes: retail fuel (Servo Saver), Brent crude (EIA), AUD/USD (RBA), and AIP wholesale prices. Run with `--loop` for 7am AEST daily execution. Bluetooth poller runs separately (continuous).
**Rationale:** Consolidates the three separate fuel refresh scripts into one orchestrated job. Each sub-script uses connect/disconnect per operation to coexist with the Bluetooth poller's write lock.
**Ruled out:** Separate cron jobs per script — harder to monitor, no consolidated log.
**Status:** Confirmed ✅

---

### DEC-023 — Aviation tab: BITRE data, all 5 capitals, 2024+ only
**Decision:** New Aviation tab using three BITRE open datasets from data.gov.au (CC-BY 3.0 AU): airport traffic (passengers + aircraft movements), domestic route stats, and on-time performance. Scope: all five capital-city airports (Melbourne, Sydney, Brisbane, Perth, Adelaide). Data filtered to 2024 onwards to keep the DB skinny (~1,700 rows total). Monthly granularity — no public Australian source provides daily passenger counts. OTP filtered to "All Airlines" aggregates only (no per-airline breakdown). Passengers and aircraft movements merged into a single `airport_monthly` table.
**Rationale:** BITRE is the authoritative free source. data.gov.au provides CSV downloads (no auth, no API key). Covering all 5 cities adds negligible data volume since the BITRE file already contains them. 2024+ cutoff keeps hosting costs minimal while giving ~2 years of trend data. Merging pax + aircraft into one table avoids a join on the same grain. "All Airlines" OTP keeps rows manageable while still showing route-level reliability.
**Ruled out:** Melbourne-only (data already includes all airports at no extra cost). Daily/weekly granularity (not available publicly — Airservices has hourly flight-level data but requires subscription request, logged as future enrichment). Per-airline OTP breakdowns (3-4x more rows for limited analytical value in V1). BITRE XLSX files (data.gov.au has equivalent CSVs, easier to parse).
**Tables:** `airport_monthly`, `domestic_routes`, `aviation_otp`
**Script:** `scripts/ingest_aviation.py`
**Status:** Confirmed ✅

---

### DEC-024 — Materialize metro core stations as permanent table
**Decision:** Replace the per-request `CREATE TEMP TABLE metro_core_stations` (which scanned the full 73M-row hourly_counts table on every API call) with a permanent DuckDB table materialized by `scripts/materialize_metro_core.py`. The script runs as the first job in `daily_refresh.py`. API endpoints now join against the permanent table directly; `create_metro_core_table()` removed from `api/db.py` and all 8 call sites (7 in traffic.py, 1 in monitor.py). Replaced with `get_metro_core_count()` which reads the row count from the permanent table.
**Rationale:** The temp table approach was the single biggest scalability weakness before going live — every page load that touched Monitor, Analysis, or weekly trend endpoints triggered a full-table scan of the largest table in the database. Materializing once daily is sufficient because the station cohort only changes when new baseline data arrives. The 967-station count is stable.
**Ruled out:** (a) In-memory cache in the API process — would break if multiple workers are used and adds process-state complexity. (b) DuckDB persistent view — views don't cache results, so the scan would still run per-query.
**Files changed:** `api/db.py`, `api/routes/traffic.py`, `api/routes/monitor.py`, `scripts/materialize_metro_core.py` (new), `scripts/daily_refresh.py`
**Status:** Confirmed ✅

---

### DEC-025 — Rewrite event-impact as single-pass query
**Decision:** Replaced the N+1 query pattern in `/api/traffic/event-impact` with a single-pass approach: one SQL query computes daily avg-per-station across all dates, then Python loops over events and filters the in-memory dict (~700 rows) for event windows and baseline comparisons. Previously, each event triggered a full CTE scan of the 73M-row hourly_counts table.
**Rationale:** The old approach ran the same massive daily aggregation N times (once per calendar event). With 11 events that's 11 full table scans per request. The new approach runs 1 scan and does the window/baseline logic in Python with dict lookups — dropping response time from multi-second to ~1s. Baseline logic also improved: now uses exact same-day-of-week matches at 1–5 week offsets rather than a date-range filter, which is a cleaner day-of-week control.
**Ruled out:** (a) Single SQL query with window functions joining events to daily — achievable but harder to read and debug than the hybrid approach, with negligible performance difference since the daily result set is small. (b) Precomputing event impact offline — unnecessary given the 1s response time.
**Files changed:** `api/routes/traffic.py` (event-impact endpoint)
**Status:** Confirmed ✅

---

### DEC-026 — Env-driven CORS origins and API URL
**Decision:** CORS origins in `api/main.py` now read from the `CORS_ORIGINS` env var (comma-separated), falling back to localhost dev defaults if unset. Frontend already had `VITE_API_URL` with a localhost fallback in `constants/index.js`; added `frontend/.env` (dev defaults) and `frontend/.env.example` (template for production). Added `CORS_ORIGINS` documentation to root `.env`. No code changes needed at deploy time — just set the two env vars for the target environment.
**Rationale:** Hardcoded localhost origins in CORS and the frontend API URL were a deploy blocker. Env vars let the same codebase run in dev and production without code edits. The fallback-to-localhost pattern means local dev continues to work with zero config.
**Ruled out:** (a) `allow_origins=["*"]` — too permissive for a public API. (b) Separate config files per environment — env vars are simpler and standard for containerised deploys.
**Files changed:** `api/main.py`, `.env`, `frontend/.env` (new), `frontend/.env.example` (new)
**Status:** Confirmed ✅

---

### DEC-027 — Parameterize all user-input SQL interpolation
**Decision:** Replaced all f-string interpolation of user-supplied query parameters with `?` parameterized queries across all API routes. Affected endpoints: `hourly-profile` (year), `daily-counts` (date_from/date_to), `heatmap` (weeks), `weekly-trend` (weeks LIMIT), `calendar-events` (date_from/date_to × 3 queries), `monitor` baseline (BASELINE_START/END), `fuel/price-chain` (months × 2 queries). For INTERVAL expressions where DuckDB doesn't support `?`, added `_weeks_ago()` and `_months_ago()` helpers that compute the cutoff date in Python. Remaining f-strings in the codebase only interpolate safe constants (`VIC_FILTER`) or programmatic clause builders that themselves use `?` params.
**Rationale:** Even with read-only connections, interpolating request strings into SQL is a bad pattern to take live. The read-only flag is a DuckDB connection setting, not a security boundary — and defence in depth is the right approach for a public URL. Parameterized queries also give DuckDB better query plan caching.
**Ruled out:** (a) Leave as-is since connection is read-only — insufficient for a public API. (b) Input validation regex on date strings — defence in depth, not a replacement for parameterization.
**Files changed:** `api/routes/traffic.py`, `api/routes/monitor.py`, `api/routes/fuel.py`
**Status:** Confirmed ✅

---

### DEC-028 — Production hardening: error handling, logging, validation, backups
**Decision:** Four pre-deployment fixes applied in one batch:
1. **API error handling + logging** (`api/main.py`): Added Python `logging` with structured format, request logging middleware (method, path, status, duration ms), and a global exception handler that returns clean JSON instead of stack traces. Debug detail gated behind `AMIP_DEBUG` env var.
2. **Startup validation** (`api/main.py`): On import, verifies DB file exists, connects, and checks for required tables (`hourly_counts`, `stations`, `metro_core_stations`, `calendar`). Fails fast with a clear error message if anything is missing.
3. **React ErrorBoundary** (`frontend/src/components/ErrorBoundary.jsx`, `main.jsx`): Class component wrapping `<App>` that catches unhandled render errors and shows a "something went wrong" fallback with a refresh button instead of a white screen.
4. **Database backup** (`scripts/backup_db.py`, added to `daily_refresh.py`): Timestamped file copy of `amip.duckdb` to `db/backups/`, configurable retention (default 7), runs as the last daily refresh job. Safe to run while API and Bluetooth poller are running.
**Rationale:** These are architecture-independent pre-deployment essentials — needed regardless of hosting choice. Addresses traps #7, #11, #18, #19 from the deployment audit.
**Files changed:** `api/main.py`, `frontend/src/main.jsx`, `frontend/src/components/ErrorBoundary.jsx` (new), `scripts/backup_db.py` (new), `scripts/daily_refresh.py`
**Status:** Confirmed ✅

---

### DEC-029 — Pre-aggregated summary tables replace hourly_counts for dashboard queries
**Decision:** Built two summary tables and rewired 11 API endpoints to query them instead of the 73M-row `hourly_counts` table:
- `daily_station_summary` (770K rows): per-station daily totals for metro core. Serves: weekly-trend, daily-counts, month-on-month, school-holiday-effect, peak-days, event-impact, weekday-drift (no — stays raw, needs hourly grain), monitor (weekly trend + baseline), fuel/traffic-overlay.
- `hourly_city_summary` (19K rows): all-station hourly city-level averages. Serves: hourly-profile, hourly-profile-multi, day-of-week, heatmap.
- `weekday-drift` and `station-profile` remain on raw `hourly_counts` (need hourly business-hours filter and per-station detail respectively).
- Monitor freshness check rewired from `hourly_counts` to `daily_station_summary`.
- `build_summaries.py` created with `--append` mode for incremental daily updates, added to `daily_refresh.py` as job #5.
- `run_script()` in `daily_refresh.py` updated to accept optional `args` parameter.
**Rationale:** 73M-row scans were 0.4–3s per request — not viable for a public URL. Summary tables reduce scan to 790K rows (93x reduction). Side-by-side testing showed 301/301 exact matches before rewiring. Response times dropped to 23–50ms for most endpoints (13x–77x faster).
**Safety net:** Raw `hourly_counts` remains in the live DB untouched. Full DuckDB backups in `db/backups/`. All 73M raw rows archived to compressed Parquet in `db/archive/` (410 MB). Any endpoint can be reverted to raw queries individually.
**Ruled out:** (a) Dropping `hourly_counts` immediately — premature, want to validate in production first. (b) Summary tables only (no raw fallback) — too risky for a first deployment. (c) Precomputing business-hours column for weekday-drift — would add complexity; 1.1s response on raw is acceptable for now.
**Files changed:** `api/routes/traffic.py`, `api/routes/monitor.py`, `api/routes/fuel.py`, `scripts/build_summaries.py` (new), `scripts/daily_refresh.py`
**Status:** Confirmed ✅

---

### DEC-030 — Complete hourly_counts independence: weekday-drift and station-profile
**Decision:** Removed the last two API endpoint dependencies on the raw `hourly_counts` table:
1. **weekday-drift**: Added `biz_hours_total` column to `daily_station_summary` (sum of hours 7–17 per station per day). Endpoint rewired to query this column instead of filtering `hourly_counts` by `hour_of_day BETWEEN 7 AND 17`. Response time: 51ms (was 1.1s). Values match raw within 0.01% (integer rounding at different aggregation stages).
2. **station-profile**: Rewired to read from Parquet archive files via `read_parquet('db/archive/hourly_counts_{year}.parquet')` instead of the `hourly_counts` table. Exact match with raw. Response time: 88ms. `ARCHIVE_DIR` exported from `api/db.py`.
3. **health endpoint**: Updated to query `daily_station_summary` row count and max date instead of `hourly_counts`.
4. **startup validation**: Now checks for `daily_station_summary` and `hourly_city_summary` instead of `hourly_counts`.
**Rationale:** With all endpoints off `hourly_counts`, the 73M-row table can be dropped from the live DB when ready, shrinking it from ~1.7 GB to ~200 MB. The Parquet archive (410 MB) retains full per-station hourly access for Explorer tab and any future reprocessing.
**Ruled out:** (a) Building a per-station hourly summary table — would be ~75M rows, same size as raw. (b) Leaving station-profile on raw — works fine but creates a dependency that blocks dropping the table.
**Files changed:** `api/main.py`, `api/db.py`, `api/routes/traffic.py`, `scripts/build_summaries.py`
**Status:** Confirmed ✅

---

### DEC-031 — Automated incremental SCATS refresh
**Decision:** Created `scripts/refresh_scats.py` for automated incremental SCATS traffic data updates, replacing the manual download-and-full-reload process (`ingest_vic_counts.py` which destructively DELETEs all VIC data before reloading). The new script:
1. Scrapes the VIC open data portal page to find the latest monthly ZIP URL
2. Downloads to `data_vic_new/scats_staging/` (skips if already cached)
3. Extracts only CSVs for dates after the latest date in DB (no full extraction)
4. INSERTs new hourly rows incrementally (no DELETE, no full reload)
5. Optionally runs `build_summaries.py --append` to update summary tables
6. Re-exports the current year's Parquet archive
Added to `daily_refresh.py` as job #4a (between aviation and summaries) with `--skip-summaries` flag so summaries are handled centrally at step #5. The portal publishes monthly ZIPs updated throughout the month, so daily runs pick up new days as they appear.
**Rationale:** The old `ingest_vic_counts.py` deletes all VIC rows then reloads from whatever directories exist — destructive and manual. For hosting, data refresh must be automated, incremental, and safe. First run successfully ingested 7 new days (March 14–20, 642K rows) bringing the Monitor tab from "Week of 9 Mar" to "Week of 16 Mar".
**Ruled out:** (a) Keeping manual download + full reload — not viable for automated hosting. (b) Building a CKAN API integration — the portal doesn't expose a usable API for ZIP resources; page scraping is simpler and the URL pattern is stable.
**Files changed:** `scripts/refresh_scats.py` (new), `scripts/daily_refresh.py`
**Status:** Confirmed ✅

---

### DEC-032 — Drop hourly_counts from live DB, compact 1,786 MB → 47 MB
**Decision:** Dropped the `hourly_counts` table (74M rows) from the live DuckDB file. Compacted via export-all-tables-to-fresh-DB approach (DuckDB VACUUM doesn't reclaim disk space). DB file went from 1,786 MB to 47 MB (97.4% reduction). Updated `refresh_scats.py` to work without `hourly_counts` — new flow processes CSVs into a temp table, then appends directly to `daily_station_summary`, `hourly_city_summary`, and the Parquet archive in a single pass. Removed the now-unnecessary `--skip-summaries` flag and `update_parquet_archive()` function. `daily_refresh.py` updated to call `refresh_scats.py` without args.
**Rationale:** All API endpoints were already independent of `hourly_counts` (DEC-029/030). The 74M-row table was dead weight — 97% of the DB file size, never queried. The Parquet archive (411 MB in `db/archive/`) retains full per-station hourly access for station-profile (Explorer tab) and any future reprocessing. DuckDB backups in `db/backups/` include pre-drop copies.
**Safety net:** Parquet archive (3 files, 411 MB total, all 74M raw rows). 4 timestamped DuckDB backups including the 1.7 GB pre-drop version. `amip_pre_drop.duckdb` (1.7 GB) on disk as an additional fallback.
**Ruled out:** (a) Keeping `hourly_counts` for "just in case" — it was 97% of the DB and zero endpoints queried it. The Parquet archive provides identical data access via `read_parquet()`. (b) VACUUM instead of export/reimport — DuckDB VACUUM marks pages as free but doesn't shrink the file.
**Files changed:** `scripts/refresh_scats.py`, `scripts/daily_refresh.py`
**Status:** Confirmed ✅

---

### DEC-033 — Restore PRIMARY KEY constraints after DB compaction
**Decision:** Recreated PRIMARY KEY constraints on `speed_observations (route_id, ts_interval)`, `bluetooth_routes (route_id)`, `bluetooth_links (link_id)`, and `tirtl_counts (ts_interval, site_id, heading, vehicle_class)`. Each table rebuilt via CREATE-INSERT-DROP-RENAME pattern. All row counts preserved (zero duplicates found).
**Rationale:** DEC-032's export-all-to-fresh-DB compaction stripped PRIMARY KEY constraints from these four tables. The Bluetooth poller uses `INSERT OR IGNORE` which requires a UNIQUE constraint — without it, DuckDB threw `Binder Error` on every insert. The poller ran for ~27 hours (Mon 18:44 to Tue 21:35) writing 0 rows per cycle. That data window is unrecoverable.
**Lesson:** After any DB rebuild/compaction, verify all table DDL — not just row counts. Add a startup check or post-compaction script that asserts expected PKs exist.
**Status:** Confirmed ✅

---

### OPEN-008 — Airservices Australia flight-level data subscription
**Question:** Should we request the Airservices "Flight Summary Data" and "Airport Performance Data" products for hourly/daily flight-level detail at Melbourne, Sydney, Brisbane, Perth?
**Options:** (a) Submit subscription request via data.airservicesaustralia.com order form, (b) Skip for now, monthly BITRE is sufficient
**Dependencies:** Pricing/access terms unclear — may be free for non-commercial use
**Trigger:** If monthly granularity proves insufficient for the Aviation tab analytics
**Status:** Open ⬜

---

### DEC-034 — Aviation tab: Melbourne routes YoY + OTP YoY + international split
**Decision:** Added four new sections to the Aviation tab: (1) Melbourne domestic routes YoY chart + table, (2) Melbourne OTP YoY chart + table with on-time/cancellation toggle, (3) stacked area dom/int passenger split with airport toggle, (4) international passengers YoY table for all 5 airports. Three new API endpoints: `/api/aviation/routes/yoy`, `/api/aviation/otp/yoy`, `/api/aviation/international`. All use existing `domestic_routes`, `aviation_otp`, and `airport_monthly` tables — no new ingestion needed.
**Rationale:** Adds time-series depth to the Aviation tab beyond static aggregates. YoY tables with month columns and % change badges match the analytical pattern used elsewhere in the dashboard. International split addresses the "overseas trips" question using data already in the DB.
**Status:** Confirmed ✅

---

### DEC-035 — No Flightradar24 integration for now
**Decision:** Deferred FR24 flight data integration. Not building a scraping-based poller (unofficial API or direct requests). The $9/month official FR24 API Explorer plan remains an option if near-real-time daily flight counts become needed.
**Rationale:** (a) Unofficial FR24 PyPI packages scrape the website, violating ToS and prone to breakage. (b) Supply chain concern — the March 2026 TeamPCP/LiteLLM PyPI compromise highlighted risks of third-party packages, though that specific attack targeted different packages via stolen maintainer credentials, not a PyPI platform breach. (c) The existing Brent→AIP→Servo Saver→Bluetooth chain already provides near-real-time oil-price-to-movement correlation for road traffic, which accounts for >80% of fuel consumption. (d) Monthly BITRE data covers aviation YoY trends adequately for dashboard purposes.
**Ruled out:** (a) FR24 unofficial Python SDK — ToS violation, fragile, supply chain risk. (b) Direct FR24 website scraping via `requests` — same ToS/fragility issues. (c) FR24 global statistics CSV download — manual, cumbersome for weekly refresh, global-only (not airport-specific).
**Revisit trigger:** If oil crisis analysis specifically needs daily airport-level flight counts that monthly BITRE can't provide.
**Status:** Confirmed ✅

---

### DEC-036 — Speed data resilience: WAL-safe deploys, Parquet archival, journald retention

**Decision:** Four measures implemented to prevent and diagnose Bluetooth speed data loss:
1. `scripts/safe_deploy.sh` — mandatory deployment script: stop bluetooth → stop refresh → stop API → clear WAL → git pull → start API → health check → start bluetooth + refresh. Prevents WAL lock conflicts that previously broke both poller and API.
2. `scripts/archive_speed.py` — incremental Parquet export of speed_observations, wired into daily refresh pipeline. First full archive: 2.77M rows, 13.5 MB ZSTD-compressed.
3. Journald retention raised from default (~31 MB) to 200 MB / 7 days via `/etc/systemd/journald.conf.d/amip.conf`. Previous retention was too short — gap root causes on Mar 23–24 and Mar 26–27 were undiagnosable.
4. Poller error handling hardened: explicit `finally` block ensures DuckDB connection is always closed, even on lock errors.

**Rationale:** Two data gaps identified (Mar 23 19:00–Mar 24 22:00, ~27h; Mar 26 21:00–Mar 27 17:00, ~19h) with no journal evidence to diagnose root cause. The Bluetooth API is real-time only — missed polls are permanently lost. On Mar 30, five rapid service restarts (08:05–08:10 CEST) caused WAL lock conflicts that broke the API endpoint entirely. The API was returning 500s until WAL was manually cleared. March 30 data was intact in DB but inaccessible via dashboard.

**Status:** Confirmed ✅

---

### DEC-034 — API response cache to eliminate poller-induced downtime
**Decision:** Add in-memory TTL cache (300s / 5 min, matching poll interval) as FastAPI middleware. All GET /api/* responses are cached; /api/health is excluded. Cache is thread-safe, keyed by URL path + query string. Cached responses served with `X-Cache: HIT` header; misses tagged `MISS`. Cache stats exposed via /api/health endpoint.
**Rationale:** The Bluetooth poller writes to DuckDB every 5 minutes, briefly locking the WAL and blocking all read-only API connections. This caused intermittent chart failures visible to frontend users. Traffic data doesn't change faster than the poll interval, so 5-minute cached responses are always current. Cache absorbs the lock window — users never see an error.
**Ruled out:** Per-endpoint caching (requires touching every route handler), Redis/external cache (overkill for single-process API), longer poll interval (reduces data freshness).
**Files:** `api/cache.py` (new), `api/main.py` (middleware + health stats)
**Status:** Confirmed ✅

---

### DEC-035 — Separate speed.duckdb for Bluetooth poller writes
**Decision:** Extract `speed_observations`, `bluetooth_routes`, and `bluetooth_links` from `amip.duckdb` into a dedicated `db/speed.duckdb`. The Bluetooth poller writes to `speed.duckdb`; the API reads from it via `get_speed_connection()`. The main `amip.duckdb` is only written to during the daily 7am refresh — effectively read-only during normal operation.
**Rationale:** Root cause of intermittent downtime was DuckDB's single-writer model: the poller's write lock on `amip.duckdb` blocked all API read connections. Separating the write target eliminates the contention entirely. Combined with DEC-034 (cache), this provides belt-and-suspenders protection — the cache covers the brief speed DB lock, and the main DB is never locked during polling.
**Ruled out:** Single DB with WAL tuning (DuckDB doesn't support concurrent read+write from separate processes), Postgres (architectural shift too large for this fix).
**Migration:** `scripts/migrate_speed_db.py` copies tables via ATTACH + CREATE TABLE AS SELECT. Safe to re-run. Old tables remain in amip.duckdb until manually dropped after verification.
**Files:** `api/db.py` (SPEED_DB_PATH + get_speed_connection), `api/routes/speed.py` (switched to get_speed_connection), `scripts/poll_bluetooth.py` (DB_PATH → speed.duckdb), `scripts/archive_speed.py` (DB_PATH → speed.duckdb), `scripts/migrate_speed_db.py` (new)
**Deploy sequence:** stop poller → git pull → run migrate_speed_db.py → restart API → start poller
**Status:** Confirmed ✅

---

### DEC-037 — Watchdog: automated service health + data freshness monitor
**Decision:** `scripts/watchdog.py` runs every 15 minutes via systemd timer (`amip-watchdog.timer`). Checks 12 items across 4 categories: 3 services (auto-restarts if dead), 4 data freshness thresholds, 4 API endpoint probes (200 + valid JSON), 1 frontend reachability check. All output to journalctl.
**Rationale:** The VACUUM operation on Apr 3 stopped `amip-bluetooth` and `amip-refresh` but only `amip-api` was restarted. 12h of speed data lost, daily refresh missed. Watchdog would have caught and auto-fixed within 15 minutes. Data freshness thresholds: speed ≤15min, fuel ≤36h, wholesale ≤72h, SCATS ≤45 days.
**Ruled out:** Cron (systemd timers have better logging via journalctl, dependency management, and survive service restarts), external monitoring (Uptime Robot etc — overkill for current scale, can't restart services).
**Files:** `scripts/watchdog.py` (new), `/etc/systemd/system/amip-watchdog.service` + `amip-watchdog.timer` (VPS)
**Status:** Confirmed ✅

---
### DEC-038 — Automated TIRTL refresh via CKAN API + file-size check

**Date:** 2026-04-14
**Status:** Implemented

**Context:** TIRTL vehicle classification data was manually ingested once (March 1–13 only). The VIC portal actually has 5 months of monthly ZIPs (Nov 2025–Mar 2026), each with its own CKAN resource ID. Files are updated mid-month and finalised around the 1st of the following month when they move to the "historical" page. The portal serves the same file regardless of URL filename — resource UUID is the key.

**Decision:** Built `refresh_tirtl.py` that:
- Queries the CKAN API (`package_show?id=tirtl-traffic-counts`) to discover all ZIP resources
- Uses HEAD request file-size comparison (same pattern as SCATS) to detect updates
- Downloads changed ZIPs, extracts daily CSVs, ingests via INSERT OR IGNORE
- Tracks state in `data_tirtl/tirtl_tracking.json`
- Also refreshes TIRTL Sites reference table on each run

Wired into `daily_refresh.py` as step 4b (after SCATS, before summaries) with 600s timeout. Added `timeout` parameter to `run_script()` for this purpose.

**Update cadence:** Monthly. DTP publishes current month on main page, updates mid-month, finalises ~1st of next month. Daily check via file-size is lightweight (HEAD request only).

**Outcome:** 5 months of data ingested (Nov 2025–Mar 2026), ~15M+ rows. Vehicle mix chart now shows full history.

### DEC-XXX — Short title
**Decision:** What was decided
**Rationale:** Why
**Ruled out:** What alternatives were considered and rejected
**Status:** Confirmed ✅
```

For open decisions:
```
### OPEN-XXX — Short title
**Question:** What needs to be decided
**Options:** Known candidates
**Dependencies:** What this depends on
**Trigger:** What event or milestone prompts this decision
**Status:** Open ⬜
```

---

*See also: `context.md` (project background), `conventions.md` (code standards), `stage.md` (current phase)*
