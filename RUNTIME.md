# RUNTIME.md — Traffic Movement

Operational documentation for running and maintaining the application.

## Starting the application

Two processes need to run simultaneously:

### API server (FastAPI)
```bash
cd "/Users/doug/Projects/Traffic Movement"
python3 -m uvicorn api.main:app --port 8000 --reload
```
- Serves on http://localhost:8000
- `--reload` watches for file changes (dev mode)
- Requires: `duckdb`, `fastapi`, `uvicorn` Python packages
- Reads from: `db/amip.duckdb` (read-only connections)

### Frontend (Vite + React)

The project folder has a space in its name ("Traffic Movement") which causes Vite's config resolver to fail. Use the symlink workaround:

```bash
# One-time setup: create symlink without spaces
ln -sfn "/Users/doug/Projects/Traffic Movement/frontend" /tmp/amip-frontend

# Start Vite via symlink
cd /tmp/amip-frontend
NODE_ENV=development npx vite --port 5173
```
- Serves on http://localhost:5173
- `NODE_ENV=development` is required — without it, npm skips devDependencies and Vite won't start
- Hot module replacement is active in dev mode
- If you ever need to reinstall packages: `cd /tmp/amip-frontend && NODE_ENV=development npm install`

### Verify everything is working
```bash
curl http://localhost:8000/api/health
```
Should return:
```json
{"status":"ok","hourly_rows":94470415,"stations":4259,"latest_data":"2026-03-13"}
```

## Data refresh

### VIC SCATS (Melbourne) — monthly

The VIC portal publishes monthly ZIP files. To add new data:

1. Download from https://opendata.transport.vic.gov.au/dataset/traffic-signal-volume-data
2. Extract the ZIP into the project root (creates a folder like `traffic_signal_volume_data_april_2026/`)
3. Run ingestion:
```bash
python3 scripts/ingest_vic_counts.py
```
This scans all `traffic_signal_volume_data_*` directories and loads any new data. Existing data is replaced (idempotent).

### NSW (Sydney) — periodic bulk download

TfNSW updates the bulk CSV periodically. To refresh:

1. Download from https://opendata.transport.nsw.gov.au (requires login)
2. Replace the files in `road_traffic_counts_hourly_permanent/`
3. Run:
```bash
python3 scripts/ingest_nsw_counts.py
```

### Weekly monitor report

After refreshing data:
```bash
python3 scripts/weekly_refresh.py
```
Prints a comparison report and saves JSON to `reports/weekly_monitor_YYYY-MM-DD.json`.

## Full rebuild from scratch

If you need to rebuild the database from raw CSV files:

```bash
cd "/Users/doug/Projects/Traffic Movement"

# 1. Recreate schema (drops and recreates all tables)
rm db/amip.duckdb
python3 scripts/create_schema.py

# 2. Load station references
python3 scripts/ingest_nsw_stations.py    # 295 Sydney permanent stations
python3 scripts/ingest_vic_stations.py    # ~3,964 Melbourne SCATS sites

# 3. Load hourly counts (takes ~20 minutes total)
python3 scripts/ingest_nsw_counts.py      # ~21M rows, ~5 minutes
python3 scripts/ingest_vic_counts.py      # ~73M rows, ~15 minutes (27 months)

# 4. Populate calendar
python3 scripts/populate_calendar.py      # holidays, school terms, events
```

## Environment

- **Python:** 3.9+ (tested on 3.14.3)
- **Node:** 25+ (tested on 25.5.0)
- **OS:** macOS (arm64)
- **DuckDB:** 1.5.0
- **Vite:** 5.x (Vite 8 has compatibility issues with plugin-react — use v5)

### Python packages
```
duckdb fastapi uvicorn pyproj pytz pandas
```
Install with: `pip3 install --break-system-packages duckdb fastapi uvicorn pyproj pytz pandas`

### npm packages (in frontend/)
```
react react-dom recharts (dependencies)
vite @vitejs/plugin-react (devDependencies)
```
Install with: `cd frontend && NODE_ENV=development npm install`

## Known issues

### Space in project folder name
The project lives in "Traffic Movement" (with a space). Vite's config resolver fails when the `.vite-temp` directory path contains spaces. The workaround is a symlink: `ln -sfn "/Users/doug/Projects/Traffic Movement/frontend" /tmp/amip-frontend`. Always start Vite from `/tmp/amip-frontend`.

### NODE_ENV required for Vite
`npm install` without `NODE_ENV=development` skips devDependencies (including Vite itself). Always prefix npm commands with `NODE_ENV=development`.

### NSW sensor degradation
Only 26 of 295 Sydney permanent stations have reliable data across 2019–2025. The API always filters to this reliable set for Sydney queries. See DEC-012 in `_context/decisions.md`.

### DuckDB file size
The database is ~6.9 GB with 94.5M rows. DuckDB handles this efficiently with read-only connections, but the file takes a few seconds to open on first query after restart.

### Vite version
Vite 8 has a `$RefreshReg$` error with `@vitejs/plugin-react` v6. Pinned to Vite 5 + plugin-react 4 which work correctly.

## File paths

| Path | Contents |
|---|---|
| `db/amip.duckdb` | Main database (6.9 GB) |
| `road_traffic_counts_hourly_permanent/` | Raw NSW CSV files (~1 GB) |
| `road_traffic_counts_station_reference.csv` | NSW station metadata |
| `traffic_signal_volume_data_*/` | Raw VIC SCATS monthly CSVs (~3.5 GB total) |
| `Traffic_Lights.csv` | VIC signal site coordinates |
| `reports/` | Weekly monitor JSON output |
