"""
AMIP API — FastAPI server for traffic data queries.

Thin, stateless API layer over DuckDB. Each endpoint queries
the amip.duckdb database and returns JSON. No business logic
lives here — just query execution and response formatting.

Run: uvicorn api.main:app --reload --port 8000
From project root: /Users/doug/Projects/Traffic Movement
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from api.db import get_connection
from api.routes import traffic, stations, monitor, speed, transport, tirtl, fuel, aviation

app = FastAPI(
    title="AMIP API",
    description="Australia Mobility Intelligence Platform — Traffic Data API",
    version="0.1.0",
)

# CORS — allow Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Mount route modules
app.include_router(traffic.router, prefix="/api/traffic", tags=["traffic"])
app.include_router(stations.router, prefix="/api/stations", tags=["stations"])
app.include_router(monitor.router, prefix="/api/monitor", tags=["monitor"])
app.include_router(speed.router)
app.include_router(transport.router)
app.include_router(tirtl.router)
app.include_router(fuel.router)
app.include_router(aviation.router)


@app.get("/api/health")
def health():
    """Health check — confirms DB is accessible and returns row counts."""
    con = get_connection()
    counts = con.execute("""
        SELECT
            (SELECT count(*) FROM hourly_counts) as hourly_rows,
            (SELECT count(*) FROM stations) as station_rows,
            (SELECT max(ts_hour)::DATE FROM hourly_counts) as latest_data
    """).fetchone()
    con.close()
    return {
        "status": "ok",
        "hourly_rows": counts[0],
        "stations": counts[1],
        "latest_data": str(counts[2]),
    }
