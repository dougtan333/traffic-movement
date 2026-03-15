# data.md — Traffic Movement
> Data sources, schemas, and verification status. Updated as sources are confirmed and integrated. No data is used in the product until it has an entry here marked verified.

---

## How to use this file

Every data source used in this project gets an entry below. A source moves through three states:

- **Candidate** ⬜ — identified, not yet assessed
- **Assessed** 🔍 — reviewed, licensing and quality checked, decision pending
- **Confirmed** ✅ — verified back to source, licensed for use, integrated or ready to integrate
- **Rejected** ❌ — assessed and ruled out, reason recorded

Never use a source in the product until it is marked **Confirmed ✅**.

---

## Confirmed sources

### SRC-001 — TfNSW Traffic Volume Counts — Hourly Permanent
**Provider:** Transport for NSW
**Portal:** https://opendata.transport.nsw.gov.au/dataset/nsw-roads-traffic-volume-counts-api
**Coverage:** ~600 permanent roadside collection stations across NSW. Sydney metro stations are the V1 target.
**Signals:** Hourly vehicle counts per station per day (columns hour_00 through hour_23). No speed data.
**Granularity:** Hourly
**History:** 2006–present (~20 years)
**Format:** Bulk CSV download (ZIP) + REST API (CKAN DataStore)
**Licensing:** Creative Commons Attribution (CC-BY) ✅
**Auth:** Free account registration required for download and API key
**Update frequency:** Bulk CSV updated periodically (last updated Feb 2026)

**Supporting tables (same dataset):**
- **Station Reference:** Geospatial coordinates, road name, suburb, postcode, device type, road number, road type, data quality rating. Essential for mapping stations to corridors and filtering to Sydney metro.
- **Yearly Summary:** Annual average daily traffic (AADT) per station. Useful for baseline calibration.
- **Hourly Sample:** Short-term counts from temporary stations (~2 week deployments). Lower priority for V1 but adds coverage in outer suburbs.

**Data quality note:** TfNSW has flagged ongoing issues with data quality and sensor availability. Service rebuild underway, no timeline set. Historical data remains available and usable.

**V1 role:** Primary vehicle count source for Sydney. Count-only charts (no speed).
**Status:** Confirmed ✅

---

### SRC-002 — VIC Traffic Signal Volume Data (SCATS)
**Provider:** Department of Transport and Planning (DTP), Victoria
**Portal:** https://opendata.transport.vic.gov.au/dataset/traffic-signal-volume-data
**Coverage:** Traffic signal locations across Victoria. Loop detectors in road surface at signalised intersections (SCATS system).
**Signals:** Vehicle counts per detector loop per lane, aggregated into 15-minute intervals.
**Granularity:** 15-minute intervals per detector per site
**History:** April 2014–present (~12 years). Annual archives (1.1–1.8 GB each) for 2014–2024. Monthly files (~125 MB each) for 2025–2026.
**Format:** Monthly ZIP downloads containing CSV files. No authentication required.
**Licensing:** Creative Commons Attribution 4.0 ✅
**Limitation:** Maximum 24 volume detectors per site. Under investigation by DTP.

**V1 role:** Primary vehicle count source for Melbourne. 15-min data aggregated to hourly to match NSW schema.
**Status:** Confirmed ✅

---

### SRC-007 — VIC Bluetooth Travel Time (Speed + Congestion)
**Provider:** DTP Victoria
**Portal:** https://opendata.transport.vic.gov.au/dataset/bluetooth-travel-time
**Coverage:** Freeways and major arterials across Melbourne. Routes defined by linked Bluetooth receiver sites.
**Signals:** travel_time (seconds), delay (seconds), speed (km/h), excess_delay, congestion (std devs from expected), data_status
**Granularity:** Per route/link, updated continuously (latest interval stats)
**History:** Real-time only — no built-in historical archive. We must poll and store.
**Format:** REST API (JSON). Base URL: api.opendata.transport.vic.gov.au/opendata/roads/bluetooth-travel-time/v1/
**Licensing:** CC-BY 4.0 (via DTP open data portal) ✅
**Auth:** Free account + API key from Transport Victoria Open Data Portal
**Geometry:** GeoJSON coordinates per route. Includes route name, primary_road_name, start_end_description, length (metres).

**V1 role:** Only source of speed/velocity data for Melbourne. Requires a polling script (every 5 min) to build historical archive. Enables speed charts, congestion tracking, travel time trends.
**Status:** Confirmed ✅

---

## Assessed sources

### SRC-008 — VIC TIRTL Traffic Counts and Vehicle Classification
**Provider:** DTP Victoria (released 9 March 2026)
**Portal:** https://opendata.transport.vic.gov.au (newly listed)
**Coverage:** Infra-Red Traffic Logger (TIRTL) devices across Victorian road network.
**Signals:** Vehicle count, vehicle classification (Austroads), speed, direction, date/time, location
**Format:** Downloadable (format TBC — needs inspection of actual files)
**Licensing:** Likely CC-BY 4.0 (DTP standard) — needs confirmation

**Assessment:** Very promising — this is the first VIC dataset that combines counts AND speed in the same source. Just released, needs data inspection to confirm format, granularity, and historical depth. If it provides historical speed data in a downloadable format, it could replace or supplement the Bluetooth polling approach.
**Status:** Assessed 🔍 — needs data inspection before confirming

---

### SRC-009 — NSW Toll Road Data (Transurban)
**Provider:** Transurban (via ACCC undertaking)
**Portal:** https://nswtollroaddata.com
**Coverage:** Sydney toll roads (M2, M4, M5, M7, Lane Cove, Cross City, Harbour Bridge/Tunnel, etc.)
**Signals:** Traffic counts from electronic toll points, per calendar month
**Format:** CSV + JSON, quarterly ZIP downloads
**Licensing:** Creative Commons Attribution 4.0 ✅

**Assessment:** Less granular than TfNSW hourly (monthly totals), but verified and high quality. Covers specific motorway corridors. Useful as enrichment layer, not primary source.
**Status:** Assessed 🔍 — available as secondary enrichment if needed

---

## Candidate sources

### SRC-005 — Google COVID-19 Community Mobility Reports
**Provider:** Google
**URL:** https://www.google.com/covid19/mobility/
**Coverage:** Global, includes Australian cities and regions
**Update frequency:** Static — reports ended post-COVID, historical archive only
**Historical depth:** February 2020–October 2022
**Format:** CSV
**Licensing:** Creative Commons Attribution 4.0
**Notes:** Excellent for COVID overlay feature (Phase 2). Shows % change in movement across categories (retail, transit, parks, residential, workplaces) relative to pre-COVID baseline.
**Status:** Candidate ⬜ — Phase 2

---

### SRC-006 — Apple Mobility Trends Reports
**Provider:** Apple
**URL:** https://covid19.apple.com/mobility
**Coverage:** Global, includes Australian cities
**Historical depth:** January 2020–April 2022
**Format:** CSV
**Licensing:** TBC
**Notes:** Complements Google mobility data. Different methodology — relative volume of directions requests.
**Status:** Candidate ⬜ — Phase 2

---

## Rejected sources

### SRC-003 — QLD DTMR Traffic Census
**Provider:** Department of Transport and Main Roads Queensland
**URL:** https://www.data.qld.gov.au/dataset/traffic-census-for-the-queensland-state-declared-road-network
**Reason:** Annual average daily traffic only — no hourly or sub-hourly granularity. Does not support time-series charting use case for V1.
**Status:** Rejected ❌ for V1 — revisit if hourly data becomes available

### SRC-010 — Main Roads WA Traffic Data
**Provider:** Main Roads Western Australia
**URL:** https://catalogue.data.wa.gov.au
**Reason:** Historic traffic data dashboard (15-min intervals, 2015–2019) has been retired. Current data is Traffic Digest with annual averages only.
**Status:** Rejected ❌ for V1

### SRC-011 — SA DIT Traffic Volumes
**Provider:** Department for Infrastructure and Transport, South Australia
**URL:** https://data.sa.gov.au/data/dataset/traffic-volumes
**Reason:** AADT only (annual average), updated weekly but no hourly breakdown. Does not support time-series charting.
**Status:** Rejected ❌ for V1

---

## Key data gap

**NSW has no public speed/velocity data.** Sydney charts in V1 will be vehicle-count-only. Melbourne gets both counts (SCATS) and speed (Bluetooth). If the TIRTL dataset proves out, Melbourne will have counts + speed + vehicle classification all in one.

To add speed data for Sydney in future, options include: TomTom API, Google Maps Platform, HERE API, or waiting for TfNSW to rebuild their service.

---

## V1 DuckDB schema

Four tables. Full schema documented in the data audit document (amip_data_audit.docx).

### stations — Unified station/site reference
Normalises NSW station reference and VIC SCATS site metadata. Composite key: `{state}_{source_id}`.
Key fields: station_id, state, city, source_id, source_system, road_name, suburb, latitude, longitude, direction, road_type, quality_rating.

### hourly_counts — Unified hourly vehicle counts (core fact table)
One row per station per hour. NSW maps directly (pivot hour columns). VIC SCATS aggregated from 15-min to hourly.
Key fields: station_id (FK), ts_hour (TIMESTAMP, local time AEST), vehicle_count, state, day_of_week, is_weekday, hour_of_day.
Primary key: (station_id, ts_hour).

### speed_observations — Speed and travel time (VIC Bluetooth, real-time polling)
Populated by polling VIC Bluetooth API. Melbourne-only for V1.
Key fields: route_id, ts_interval, speed_kmh, travel_time_sec, delay_sec, congestion_index, data_status, route_length_m.

### calendar — Date dimension and context signals
Pre-populated lookup. One row per date. Joins contextual signals to any date.
Key fields: date, day_of_week, is_weekday, week_number, month, year, is_public_holiday_nsw, is_public_holiday_vic, is_school_holiday_nsw, is_school_holiday_vic, event_name, season.

---

## Data pipeline notes

- All raw data lives in project root as extracted CSV directories
- DuckDB database: `db/amip.duckdb` (6.9 GB)
- Ingestion scripts in `scripts/`: each has isolated transform logic, can swap CSV source for API
- Historical snapshots retained — never overwrite, always append or version
- Bluetooth speed data: polling script needed to build historical archive (Phase 2)

### Current database state (as of 15 March 2026)

| Table | Rows | Coverage |
|---|---|---|
| stations | 4,259 | 295 Sydney permanent + 3,964 Melbourne SCATS-matched |
| hourly_counts | 94,470,415 | NSW: 21.1M (2006–Feb 2026, 295 stations) / VIC: 73.4M (Jan 2024–Mar 2026, 27 months, ~3,860 stations) |
| calendar | 2,557 | 2020–2026 with holidays, school terms, events |
| speed_observations | 0 | Awaiting Bluetooth polling script |
| bluetooth_routes | 0 | Awaiting Bluetooth polling script |
| DB file size | 6.9 GB | |

### Ingestion scripts

| Script | Source | Target | Notes |
|---|---|---|---|
| create_schema.py | — | All tables | Idempotent, IF NOT EXISTS |
| ingest_nsw_stations.py | station reference CSV | stations | Sydney permanent only |
| ingest_vic_stations.py | Traffic Lights CSV | stations | CRS reprojection EPSG:3111→4326 |
| ingest_nsw_counts.py | hourly permanent CSVs | hourly_counts | Unpivots 24 hour columns |
| ingest_vic_counts.py | SCATS monthly CSVs | hourly_counts | Aggregates 15-min→hourly, sums detectors |
| populate_calendar.py | Hardcoded dates | calendar | Holidays, school terms, events |
| weekly_refresh.py | hourly_counts (query) | stdout + JSON report | Fuel crisis tracker — weekly baseline comparison |

### Monitoring tools

**`scripts/weekly_refresh.py`** — Weekly fuel crisis traffic monitor.
- Compares latest week's weekday avg/station against Feb 2026 baseline
- Also compares vs prior week and vs same week last year
- Uses reliable network (26 stations) for Sydney, full SCATS network for Melbourne
- Outputs structured report to stdout and saves JSON to `reports/`
- Run after downloading and ingesting new SCATS data

**`reports/`** — JSON output from weekly monitor runs. One file per run date.

### Key findings from data inspection

- **NSW sensor degradation is severe:** only 63 stations reporting in 2026 (was 200+ in 2010–2018). Stations like Military Road Mosman show -59% drops that are sensor failure, not traffic changes. A "reliable network" of 26 stations was curated for historical comparison (DEC-012).
- VIC zero-volume detectors: 61% of raw rows — handled by aggregating to site level (DEC-013)
- VIC coordinates in EPSG:3111 (VicGrid94), converted to WGS84 in ingestion (DEC-014)
- NSW hourly data has ~5% null hours (sensor offline) — normal, no imputation needed
- NSW station reference join: 75% match rate (orphans are decommissioned stations)
- VIC SCATS-to-Traffic Lights join: 84% match rate (unmatched sites lack signal infrastructure)
- VIC SCATS network is healthy — ~3,860 stations reporting consistently across all 27 months
- Sydney traffic at ~92% of pre-COVID levels (reliable network, 2025 vs 2019)
- Melbourne traffic stable: 2024 and 2025 profiles nearly identical

### API-based refresh design (future)

Ingestion scripts separate data loading from transformation. To switch to API:
- NSW: Replace `read_csv_auto(glob)` with CKAN DataStore API call filtered by date range
- VIC: Replace monthly ZIP download with latest month fetch + extract
- Transform logic (unpivot, aggregate, join) is identical regardless of source

---

## Data research priorities (next actions)

1. ✅ ~~Identify and verify traffic data sources for NSW and VIC~~ — Done
2. ✅ ~~Register for TfNSW and VIC portal accounts~~ — Done
3. ✅ ~~Download and inspect NSW hourly permanent data~~ — Done, loaded 21.1M rows
4. ✅ ~~Download and inspect VIC SCATS data~~ — Done, loaded 73.4M rows (27 months)
5. ❌ TIRTL dataset not yet available for download — revisit when published
6. Build API-based incremental refresh for both states
7. Set up Bluetooth polling script for VIC speed data

---

*See also: `decisions.md` DEC-007 (data source decision), `conventions.md` (query file standards), `memory.md` (current priorities)*
