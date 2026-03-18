"""
Speed data API routes — serves Bluetooth travel time data for Melbourne.
Supports filtering by road name, freeway/arterial, and corridor.
"""
from typing import Optional
from fastapi import APIRouter, Query
from ..db import get_connection

router = APIRouter(prefix="/api/speed", tags=["speed"])


def _link_filter(road: Optional[str], freeway_only: bool):
    """Build a SQL WHERE clause fragment + params for link filtering."""
    clauses = ["so.speed_kmh > 0"]
    params = []
    if road:
        clauses.append("bl.road_name = ?")
        params.append(road)
    if freeway_only:
        clauses.append("bl.is_freeway = true")
    return " AND ".join(clauses), params


@router.get("/roads")
def speed_roads():
    """List available roads with link counts, for the filter dropdown."""
    con = get_connection()
    rows = con.execute("""
        SELECT road_name, count(*) as links, bool_or(is_freeway) as is_freeway
        FROM bluetooth_links
        WHERE road_name != ''
        GROUP BY road_name
        HAVING count(*) >= 3
        ORDER BY count(*) DESC
    """).fetchall()
    con.close()
    return {
        "roads": [
            {"name": r[0], "links": r[1], "is_freeway": r[2]}
            for r in rows
        ],
    }


@router.get("/snapshot")
def speed_snapshot(
    road: Optional[str] = Query(None, description="Filter to a specific road"),
    freeways: bool = Query(False, description="Show freeways only"),
):
    """Latest speed snapshot — optionally filtered by road or freeway."""
    con = get_connection()
    latest = con.execute("SELECT max(ts_interval) FROM speed_observations").fetchone()[0]
    if not latest:
        con.close()
        return {"status": "no_data", "message": "No speed data yet"}

    filt, filt_params = _link_filter(road, freeways)
    join = "JOIN bluetooth_links bl ON so.route_id = bl.link_id"

    summary = con.execute(f"""
        SELECT
            count(*) as links,
            avg(so.speed_kmh)::int as avg_speed,
            min(so.speed_kmh) as min_speed,
            max(so.speed_kmh) as max_speed,
            avg(so.delay_sec)::int as avg_delay,
            count(*) FILTER (WHERE so.speed_kmh < 20) as slow_links,
            count(*) FILTER (WHERE so.speed_kmh >= 20 AND so.speed_kmh < 40) as moderate_links,
            count(*) FILTER (WHERE so.speed_kmh >= 40) as free_flow_links
        FROM speed_observations so {join}
        WHERE so.ts_interval = ? AND {filt}
    """, [latest] + filt_params).fetchone()

    slowest = con.execute(f"""
        SELECT so.route_id, bl.link_name, so.speed_kmh, so.travel_time_sec,
               so.delay_sec, so.route_length_m
        FROM speed_observations so {join}
        WHERE so.ts_interval = ? AND {filt}
        ORDER BY so.speed_kmh ASC
        LIMIT 10
    """, [latest] + filt_params).fetchall()
    con.close()

    filter_label = road or ("Freeways" if freeways else "All links")

    return {
        "timestamp": str(latest),
        "filter": filter_label,
        "summary": {
            "links": summary[0],
            "avg_speed_kmh": summary[1],
            "min_speed_kmh": summary[2],
            "max_speed_kmh": summary[3],
            "avg_delay_sec": summary[4],
            "slow_links": summary[5],
            "moderate_links": summary[6],
            "free_flow_links": summary[7],
        },
        "slowest": [
            {"link_id": r[0], "name": r[1], "speed_kmh": r[2],
             "travel_time_sec": r[3], "delay_sec": r[4], "length_m": r[5]}
            for r in slowest
        ],
    }


@router.get("/trend")
def speed_trend(
    hours: int = Query(4, ge=1, le=48),
    road: Optional[str] = Query(None, description="Filter to a specific road"),
    freeways: bool = Query(False, description="Show freeways only"),
):
    """Speed trend over the last N hours — optionally filtered."""
    con = get_connection()
    filt, filt_params = _link_filter(road, freeways)
    join = "JOIN bluetooth_links bl ON so.route_id = bl.link_id"

    rows = con.execute(f"""
        SELECT
            so.ts_interval,
            avg(so.speed_kmh)::int as avg_speed,
            count(*) as links_reporting,
            count(*) FILTER (WHERE so.speed_kmh < 20) as slow_links
        FROM speed_observations so {join}
        WHERE so.ts_interval >= (SELECT max(ts_interval) FROM speed_observations) - INTERVAL '{hours} hours'
          AND {filt}
        GROUP BY so.ts_interval
        ORDER BY so.ts_interval
    """, filt_params).fetchall()
    con.close()

    return {
        "hours": hours,
        "filter": road or ("Freeways" if freeways else "All links"),
        "intervals": len(rows),
        "data": [
            {"ts": str(r[0]), "avg_speed": r[1], "links": r[2], "slow_links": r[3]}
            for r in rows
        ],
    }
