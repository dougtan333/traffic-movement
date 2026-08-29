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
from fastapi.responses import JSONResponse, Response

from api.db import get_connection, get_speed_connection, DB_PATH, SPEED_DB_PATH
from api.routes import traffic, stations, monitor, speed, transport, tirtl, fuel, aviation
from api import cache

# ---------------------------------------------------------------------------
# Logging — structured, timestamp + endpoint + duration.
# Configured before anything else so .env loading can report its own failures;
# launchd sends this stream to logs/com.amip.api.log.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("amip")

# ---------------------------------------------------------------------------
# Environment — systemd injected .env via EnvironmentFile= on the VPS; launchd has no
# equivalent, so the API loads .env itself. Same pattern as scripts/poll_bluetooth.py.
#
# This used to fail silently (finding I1): a missing or malformed .env left
# CORS_ORIGINS unset, the app fell back to localhost-only origins, /api/health
# still returned 200 and the watchdog — which probes with `requests`, sending no
# Origin header and triggering no preflight — reported everything green. The
# only visible symptom was melbtraffic.com rendering empty charts. Both the
# resolved origins and any failure to reach .env are now logged, so one grep of
# logs/com.amip.api.log answers "why is CORS wrong".
# ---------------------------------------------------------------------------
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

try:
    from dotenv import load_dotenv
except ImportError:
    # This is the branch that actually runs — python-dotenv is not installed in
    # the venv and is not in requirements.txt.
    def load_dotenv(dotenv_path=ENV_PATH):
        """Minimal .env reader: KEY=VALUE lines, # comments, no interpolation."""
        env_path = Path(dotenv_path)
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

if ENV_PATH.exists():
    logger.info("Loading environment from %s", ENV_PATH)
else:
    logger.error(
        ".env NOT FOUND at %s — every setting falls back to its built-in default, "
        "including CORS_ORIGINS. If this is the production host, melbtraffic.com "
        "will receive no Access-Control-Allow-Origin header and its charts will "
        "render empty while /api/health still returns 200. Restore the file and "
        "restart the API.", ENV_PATH)

load_dotenv(ENV_PATH)

# ---------------------------------------------------------------------------
# Startup validation (#11) — fail fast if DB or key tables are missing
# ---------------------------------------------------------------------------
def _validate_db():
    """Check DB files exist and critical tables are present."""
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

    # Speed DB — warn but don't block startup (main dashboard works without it)
    if not SPEED_DB_PATH.exists():
        logger.warning("Speed database not found: %s — /api/speed/* endpoints will fail. "
                       "Run scripts/migrate_speed_db.py to create it.", SPEED_DB_PATH)
    else:
        try:
            scon = get_speed_connection()
            scon.close()
            logger.info("Speed DB validated: %s", SPEED_DB_PATH.name)
        except Exception as e:
            logger.warning("Speed DB connection failed: %s — speed endpoints may be unavailable", e)

_validate_db()

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Melbourne Traffic Monitor API",
    description="Victorian transport data API — traffic counts, speed, fuel, aviation",
    version="0.1.0",
)

# CORS — origins from env (comma-separated) with local dev fallbacks.
# Production: set CORS_ORIGINS="https://amip.example.com" in .env
_default_origins = "http://localhost:5173,http://localhost:5174,http://localhost:3000"
_cors_env = os.environ.get("CORS_ORIGINS")
_origins = [o.strip() for o in (_cors_env or _default_origins).split(",") if o.strip()]

# Log the resolved list either way. A fallback to the dev defaults is an error,
# not a warning: on the production host it means the public site gets no CORS
# header, and nothing else in the stack notices (finding I1).
if _cors_env:
    logger.info("CORS origins (from CORS_ORIGINS): %s", ", ".join(_origins))
else:
    logger.error(
        "CORS_ORIGINS is not set — falling back to local dev origins only: %s. "
        "Any browser request from a production hostname will be blocked. "
        "Check that %s exists and contains a CORS_ORIGINS= line.",
        ", ".join(_origins), ENV_PATH)

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
    # Tag cached responses in log
    cached = response.headers.get("X-Cache", "")
    suffix = f" [CACHE {cached}]" if cached else ""
    logger.info("%s %s %d %.0fms%s",
                request.method, request.url.path, response.status_code,
                duration_ms, suffix)
    return response


# ---------------------------------------------------------------------------
# Response cache middleware — serves cached JSON during DB lock windows.
# Caches all GET /api/* responses for 5 minutes (matches poll interval).
# Skips /api/health so it always reflects live DB state.
# ---------------------------------------------------------------------------
_NO_CACHE_PATHS = {"/api/health"}
_origins_set = set(_origins)  # for fast lookup in cache middleware

@app.middleware("http")
async def cache_middleware(request: Request, call_next):
    # Only cache GET requests under /api/
    if request.method != "GET" or not request.url.path.startswith("/api/"):
        return await call_next(request)

    # Skip health and any other uncacheable paths
    if request.url.path in _NO_CACHE_PATHS:
        return await call_next(request)

    # Build CORS headers for this request (BaseHTTPMiddleware interferes
    # with CORSMiddleware's ASGI-level header injection, so we add them
    # directly to both HIT and MISS responses).
    origin = request.headers.get("origin", "")
    cors_headers = {}
    if origin and origin in _origins_set:
        cors_headers["access-control-allow-origin"] = origin
        cors_headers["vary"] = "Origin"

    # Cache key = path + sorted query string for deterministic keys
    qs = str(request.url.query) if request.url.query else ""
    cache_key = f"{request.url.path}?{qs}" if qs else request.url.path

    # Check cache
    hit = cache.get(cache_key)
    if hit is not None:
        body, content_type = hit
        return Response(
            content=body,
            media_type=content_type,
            headers={**cors_headers, "X-Cache": "HIT"},
        )

    # Miss — forward to endpoint
    response = await call_next(request)

    # Only cache successful JSON responses
    if response.status_code == 200:
        # Read the streaming response body
        body_chunks = []
        async for chunk in response.body_iterator:
            if isinstance(chunk, bytes):
                body_chunks.append(chunk)
            else:
                body_chunks.append(chunk.encode("utf-8"))
        body = b"".join(body_chunks)

        content_type = response.headers.get("content-type", "application/json")
        cache.put(cache_key, (body, content_type))

        return Response(
            content=body,
            status_code=200,
            media_type=content_type,
            headers={**cors_headers, "X-Cache": "MISS"},
        )

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
        "cache": cache.stats(),
    }
