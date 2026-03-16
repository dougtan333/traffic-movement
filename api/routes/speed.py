"""
Speed data API routes — serves Bluetooth travel time data for Melbourne.
"""
from fastapi import APIRouter, Query
from ..db import get_connection

router = APIRouter(prefix="/api/speed", tags=["speed"])


@router.get("/snapshot")
def speed_snapshot():
    """
    Latest speed snapshot across the Melbourne Bluetooth network.
    Returns network-wide summary plus per-link details for the most recent interval.
    """
    con = get_connection()
    latest = con.execute("SELECT max(ts_interval) FROM speed_observations").fetchone()[0]
    if not latest:
        con.close()
        return {"status": "no_data", "message": "No speed data yet — poller may not be running"}

    summary = con.execute("""
        SELECT
            count(*) as links,
            avg(speed_kmh)::int as avg_speed,
            min(speed_kmh) as min_speed,
            max(speed_kmh) as max_speed,
            avg(delay_sec)::int as avg_delay,
            count(*) FILTER (WHERE speed_kmh < 20) as slow_links,
            count(*) FILTER (WHERE speed_kmh >= 20 AND speed_kmh < 40) as moderate_links,
            count(*) FILTER (WHERE speed_kmh >= 40) as free_flow_links
        FROM speed_observations
        WHERE ts_interval = ?
          AND speed_kmh > 0
    """, [latest]).fetchone()

    # Slowest 10 links
    slowest = con.execute("""
        SELECT route_id, speed_kmh, travel_time_sec, delay_sec, route_length_m
        FROM speed_observations
        WHERE ts_interval = ? AND speed_kmh > 0
        ORDER BY speed_kmh ASC
        LIMIT 10
    """, [latest]).fetchall()

    con.close()

    return {
        "timestamp": str(latest),
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
            {"link_id": r[0], "speed_kmh": r[1], "travel_time_sec": r[2],
             "delay_sec": r[3], "length_m": r[4]}
            for r in slowest
        ],
    }


@router.get("/trend")
def speed_trend(hours: int = Query(4, ge=1, le=48)):
    """
    Network-wide average speed trend over the last N hours.
    Returns one point per 5-min interval.
    """
    con = get_connection()
    rows = con.execute(f"""
        SELECT
            ts_interval,
            avg(speed_kmh)::int as avg_speed,
            count(*) as links_reporting,
            count(*) FILTER (WHERE speed_kmh < 20) as slow_links
        FROM speed_observations
        WHERE ts_interval >= (SELECT max(ts_interval) FROM speed_observations) - INTERVAL '{hours} hours'
          AND speed_kmh > 0
        GROUP BY ts_interval
        ORDER BY ts_interval
    """).fetchall()
    con.close()

    return {
        "hours": hours,
        "intervals": len(rows),
        "data": [
            {"ts": str(r[0]), "avg_speed": r[1], "links": r[2], "slow_links": r[3]}
            for r in rows
        ],
    }
