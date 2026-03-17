"""
TIRTL data endpoints — vehicle counts, classification, and speed from TIRTL sensors.
Covers 288 sites across Victorian road network (mostly freeways).
"""
from typing import Optional
from fastapi import APIRouter, Query
from ..db import get_connection

router = APIRouter(prefix="/api/tirtl", tags=["tirtl"])

VEHICLE_CLASSES = {
    0: 'Unknown', 1: 'Car', 2: 'Car+trailer', 3: 'Rigid 2-axle',
    4: 'Rigid 3-axle', 5: 'Rigid 4+ axle', 6: 'Artic 3-4 axle',
    7: 'Artic 5-axle', 8: 'Artic 6-axle', 9: 'Artic 7+ axle',
    10: 'B-double', 11: 'Road train', 13: 'Bus', 14: 'Bus 3-axle',
}


@router.get("/vehicle-mix")
def vehicle_mix():
    """Daily vehicle class breakdown — cars vs trucks vs buses over time."""
    con = get_connection()
    rows = con.execute("""
        SELECT
            ts_interval::DATE as date,
            CASE
                WHEN vehicle_class = 1 THEN 'Cars'
                WHEN vehicle_class = 2 THEN 'Cars+trailer'
                WHEN vehicle_class IN (3,4,5) THEN 'Rigid trucks'
                WHEN vehicle_class IN (6,7,8,9,10,11) THEN 'Articulated/B-double'
                WHEN vehicle_class IN (13,14) THEN 'Buses'
                ELSE 'Other'
            END as category,
            SUM(volume) as total
        FROM tirtl_counts
        GROUP BY 1, 2
        ORDER BY 1, 2
    """).fetchall()
    con.close()

    # Reshape: one row per date with columns per category
    dates = {}
    for r in rows:
        d = str(r[0])
        if d not in dates:
            dates[d] = {"date": d}
        dates[d][r[1]] = r[2]

    return {"data": list(dates.values())}


@router.get("/speed-by-hour")
def speed_by_hour():
    """Hourly average speed profile from TIRTL sensors, weekdays vs weekends."""
    con = get_connection()
    rows = con.execute("""
        SELECT
            EXTRACT(HOUR FROM ts_interval)::INT as hour,
            CASE WHEN ISODOW(ts_interval::DATE) <= 5 THEN 'weekday' ELSE 'weekend' END as day_type,
            (SUM(volume * avg_speed_kmh) / NULLIF(SUM(volume), 0))::INT as weighted_avg_speed,
            SUM(volume) as total_volume
        FROM tirtl_counts
        WHERE avg_speed_kmh > 0 AND avg_speed_kmh < 200
        GROUP BY 1, 2
        ORDER BY 1, 2
    """).fetchall()
    con.close()

    data = []
    for r in rows:
        data.append({
            "hour": r[0],
            "day_type": r[1],
            "avg_speed": r[2],
            "volume": r[3],
        })
    return {"data": data}


@router.get("/crisis-comparison")
def crisis_comparison():
    """
    Compare pre-crisis (1-2 Mar, weekend baseline) vs post-crisis (8-13 Mar)
    by vehicle category. Shows whether cars dropped while trucks stayed constant.
    """
    con = get_connection()
    rows = con.execute("""
        SELECT
            CASE
                WHEN ts_interval::DATE <= '2026-03-02' THEN 'pre_crisis'
                WHEN ts_interval::DATE >= '2026-03-08' THEN 'post_crisis'
                ELSE 'transition'
            END as period,
            CASE WHEN ISODOW(ts_interval::DATE) <= 5 THEN 'weekday' ELSE 'weekend' END as day_type,
            CASE
                WHEN vehicle_class = 1 THEN 'Cars'
                WHEN vehicle_class IN (3,4,5,6,7,8,9,10,11) THEN 'Trucks'
                ELSE 'Other'
            END as category,
            SUM(volume) as total,
            COUNT(DISTINCT ts_interval::DATE) as days
        FROM tirtl_counts
        WHERE ts_interval::DATE != '2026-03-03'
          AND ts_interval::DATE NOT BETWEEN '2026-03-03' AND '2026-03-07'
        GROUP BY 1, 2, 3
        ORDER BY 1, 2, 3
    """).fetchall()
    con.close()

    data = []
    for r in rows:
        avg_daily = r[3] // r[4] if r[4] > 0 else 0
        data.append({
            "period": r[0], "day_type": r[1], "category": r[2],
            "total": r[3], "days": r[4], "avg_daily": avg_daily,
        })
    return {"data": data}
