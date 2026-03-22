"""
AMIP API — FastAPI server for traffic data queries.

Thin, stateless API layer over DuckDB. Each endpoint queries
the amip.duckdb database and returns JSON. No business logic
lives here — just query execution and response formatting.

Run: uvicorn api.main:app --reload --port 8000
From project root: /Users/doug/Projects/Traffic Movement
"""

import logging
import os
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.db import get_connection, DB_PATH
from api.routes import traffic, stations, monitor, speed, transport, tirtl, fuel, aviation

# ---------------------------------------------------------------------------
# Logging — structured, timestamp + endpoint + duration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("amip")

# ---------------------------------------------------------------------------
# Startup validation (#11) — fail fast if DB or key tables are missing
# ---------------------------------------------------------------------------
def _validate_db():
    """Check DB file exists and critical tables are present."""
    if not DB_PATH.exists():
        raise RuntimeError(f"Database not found: {DB_PATH}")
    try:
        con = get_connection()
        tables = [r[0] for r in con.execute(
            "SELECT table_name FROM duckdb_tables() WHERE schema_name='main'"
        ).fetchall()]
        con.close()
    except Exception as e:
        raise RuntimeError(f"Cannot connect to database: {e}")

    required = ["daily_station_summary", "hourly_city_summary", "stations",
                 "metro_core_stations", "calendar"]
    missing = [t for t in required if t not in tables]
    if missing:
        raise RuntimeError(
            f"Missing required tables: {', '.join(missing)}. "
            f"Run materialize_metro_core.py and check data ingestion."
        )
    logger.info("DB validated: %s (%d tables, including %s)",
                DB_PATH.name, len(tables), ", ".join(required))

_validate_db()

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AMIP API",
    description="Australia Mobility Intelligence Platform — Traffic Data API",
    version="0.1.0",
)

# CORS — origins from env (comma-separated) with local dev fallbacks.
# Production: set CORS_ORIGINS="https://amip.example.com" in .env
_default_origins = "http://localhost:5173,http://localhost:5174,http://localhost:3000"
_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", _default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request logging middleware — logs every request with duration
# ---------------------------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    logger.info("%s %s %d %.0fms",
                request.method, request.url.path, response.status_code, duration_ms)
    return response


# ---------------------------------------------------------------------------
# Global exception handler (#7) — catch unhandled errors, return clean JSON
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)
                 if os.environ.get("AMIP_DEBUG") else None},
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
            (SELECT count(*) FROM daily_station_summary) as summary_rows,
            (SELECT count(*) FROM stations) as station_rows,
            (SELECT max(day) FROM daily_station_summary) as latest_data
    """).fetchone()
    con.close()
    return {
        "status": "ok",
        "summary_rows": counts[0],
        "stations": counts[1],
        "latest_data": str(counts[2]),
    }
