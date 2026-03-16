"""
Transport data endpoints — PT patronage and vehicle fleet.
Serves Victorian public transport and vehicle registration data.
"""
from fastapi import APIRouter, Query
from ..db import get_connection

router = APIRouter(prefix="/api/transport", tags=["transport"])


@router.get("/pt-monthly")
def pt_monthly():
    """Monthly PT patronage by mode — all available months."""
    con = get_connection()
    rows = con.execute("""
        SELECT year, month, month_name,
               metro_train, metro_tram, metro_bus,
               regional_train, regional_coach, regional_bus
        FROM pt_patronage_monthly
        ORDER BY year, month
    """).fetchall()
    con.close()

    return {
        "data": [
            {
                "year": r[0], "month": r[1], "month_name": r[2],
                "label": f"{r[2][:3]} {r[0]}",
                "metro_train": r[3], "metro_tram": r[4], "metro_bus": r[5],
                "regional_train": r[6], "regional_coach": r[7], "regional_bus": r[8],
                "total": r[3] + r[4] + r[5] + r[6] + r[7] + r[8],
            }
            for r in rows
        ],
    }


@router.get("/pt-daytype")
def pt_daytype(year: int = Query(2025)):
    """Avg daily PT patronage by day type and mode for a given year."""
    con = get_connection()
    rows = con.execute("""
        SELECT day_type, mode, avg(pax_daily)::int as avg_daily
        FROM pt_patronage_daytype
        WHERE year = ?
        GROUP BY day_type, mode
        ORDER BY day_type, mode
    """, [year]).fetchall()
    con.close()

    data = {}
    for r in rows:
        dt = r[0]
        if dt not in data:
            data[dt] = {}
        data[dt][r[1]] = r[2]

    return {"year": year, "data": data}


@router.get("/fleet")
def fleet():
    """Vehicle fleet breakdown by fuel type."""
    con = get_connection()
    rows = con.execute("""
        SELECT quarter, fuel_type, vehicle_count
        FROM vehicle_registrations
        ORDER BY vehicle_count DESC
    """).fetchall()
    con.close()

    total = sum(r[2] for r in rows)
    return {
        "quarter": rows[0][0] if rows else None,
        "total": total,
        "breakdown": [
            {"fuel_type": r[1], "count": r[2], "pct": round(r[2] / total * 100, 1)}
            for r in rows
        ],
    }
