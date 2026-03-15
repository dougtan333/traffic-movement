# Traffic Movement

Australia Mobility Intelligence Platform — tracking traffic and people movement across Sydney and Melbourne.

Takes publicly available traffic sensor data, normalises it into a unified schema, and presents it through an interactive dashboard with historical comparisons, seasonal analysis, and real-time event tracking (currently monitoring the March 2026 fuel crisis).

## Quick start

Two terminals needed — API and frontend:

```bash
# Terminal 1: API server
cd "/Users/doug/Projects/Traffic Movement"
python3 -m uvicorn api.main:app --port 8000

# Terminal 2: Frontend dev server (symlink avoids space-in-path issue)
ln -sfn "/Users/doug/Projects/Traffic Movement/frontend" /tmp/amip-frontend
cd /tmp/amip-frontend
NODE_ENV=development npx vite --port 5173
```

Open http://localhost:5173

## Tech stack

| Layer | Tool |
|---|---|
| Data | DuckDB (`db/amip.duckdb`, 6.9 GB) |
| API | FastAPI (Python) |
| Frontend | React + Recharts (Vite) |
| Ingestion | Python scripts in `scripts/` |

## Data

94.5 million rows of hourly traffic counts across two cities:

- **Sydney (NSW):** 26 reliable stations, 2006–Feb 2026. Source: TfNSW hourly permanent counts. Count-only (no speed data).
- **Melbourne (VIC):** ~3,860 SCATS signal sites, Jan 2024–Mar 2026. Source: VIC DTP Traffic Signal Volume Data.
- **Calendar:** Public holidays, school terms, major events (2020–2026).

All data is CC-BY licensed from state government open data portals.

## Project structure

```
Traffic Movement/
  _context/           Claude context files (stage, decisions, memory, data, conventions)
  api/                FastAPI server
    main.py           App entry point, CORS, health check
    db.py             DuckDB connection helper
    constants.py      Reliable station IDs, config
    routes/
      traffic.py      Hourly profiles, weekly trends, daily counts, day-of-week
      stations.py     Station reference with coordinates
      monitor.py      Weekly fuel crisis tracker
  frontend/           React app (Vite)
    src/
      components/     One component per folder (CitySelector, MetricCards, charts)
      hooks/          useTrafficData.js — data fetching hook
      constants/      API URL, city colours, year colours
      styles/         Global CSS
  scripts/            Data ingestion and monitoring
    create_schema.py
    ingest_nsw_stations.py
    ingest_nsw_counts.py
    ingest_vic_stations.py
    ingest_vic_counts.py
    populate_calendar.py
    weekly_refresh.py
    inspect_data.py
  db/                 DuckDB database file
  reports/            Weekly monitor JSON output
```

## API endpoints

All endpoints return JSON. Base URL: `http://localhost:8000`

| Endpoint | Description |
|---|---|
| `GET /api/health` | DB status, row counts, latest data date |
| `GET /api/traffic/hourly-profile?city=sydney&year=2025` | Weekday hourly avg per station |
| `GET /api/traffic/hourly-profile-multi?city=sydney&years=2019,2025` | Multi-year overlay |
| `GET /api/traffic/weekly-trend?city=melbourne&weeks=26` | Weekly weekday avg trend |
| `GET /api/traffic/daily-counts?city=melbourne&date_from=2026-02-01&date_to=2026-03-31` | Daily totals with calendar context |
| `GET /api/traffic/day-of-week?city=sydney&year=2025` | Mon–Sun averages (business hours) |
| `GET /api/stations/?city=sydney` | Station list with coordinates |
| `GET /api/monitor/` | Weekly fuel crisis comparison report |

Sydney always uses the reliable network (26 stations with consistent data 2019–2025). Melbourne uses the full SCATS network.

## Weekly data refresh

To update with new SCATS data (monitoring the fuel crisis):

1. Download the latest monthly ZIP from https://opendata.transport.vic.gov.au/dataset/traffic-signal-volume-data
2. Extract to the project folder (alongside existing monthly folders)
3. Run ingestion and monitor:

```bash
cd "/Users/doug/Projects/Traffic Movement"
python3 scripts/ingest_vic_counts.py
python3 scripts/weekly_refresh.py
```

## Prerequisites

```bash
pip3 install --break-system-packages duckdb fastapi uvicorn pyproj pytz pandas
cd frontend && NODE_ENV=development npm install
```

## Context files

Project context for Claude sessions lives in `_context/`. Start with `stage.md` and `memory.md` to understand the current state.

See also: [RUNTIME.md](RUNTIME.md) for operational details.
