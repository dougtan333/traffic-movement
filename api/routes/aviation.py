"""
Aviation endpoints — airport passenger trends, domestic routes, on-time performance.
Serves BITRE monthly data for the five AMIP capital-city airports (2024+).
"""
from fastapi import APIRouter, Query
from typing import Optional
from ..db import get_connection

router = APIRouter(prefix="/api/aviation", tags=["aviation"])

# City colour scheme (matches AMIP standard)
CITY_COLOURS = {
    "MELBOURNE": "#1B3A5C",
    "SYDNEY": "#2A9D8F",
    "BRISBANE": "#E9C46A",
    "PERTH": "#F4A261",
    "ADELAIDE": "#6D2E46",
}


@router.get("/passengers")
def passengers(airport: Optional[str] = Query(None)):
    """Monthly passenger totals per airport, with domestic/international split.
    Optional airport filter (e.g. MELBOURNE). Returns all 5 airports if omitted."""
    con = get_connection()
    where = "WHERE airport = ?" if airport else ""
    params = [airport.upper()] if airport else []
    rows = con.execute(f"""
        SELECT airport, year, month,
               dom_pax_total, int_pax_total, pax_total,
               dom_acm_total, int_acm_total, acm_total
        FROM airport_monthly
        {where}
        ORDER BY airport, year, month
    """, params).fetchall()
    con.close()

    return {
        "data": [
            {
                "airport": r[0], "year": r[1], "month": r[2],
                "dom_pax": r[3], "int_pax": r[4], "total_pax": r[5],
                "dom_flights": r[6], "int_flights": r[7], "total_flights": r[8],
            }
            for r in rows
        ],
        "colours": CITY_COLOURS,
    }


@router.get("/passengers/yoy")
def passengers_yoy():
    """Year-on-year comparison: each month's pax vs the same month last year."""
    con = get_connection()
    rows = con.execute("""
        SELECT a.airport, a.year, a.month, a.pax_total,
               b.pax_total as prev_year_pax,
               round((a.pax_total - b.pax_total) * 100.0 / nullif(b.pax_total, 0), 1) as yoy_pct
        FROM airport_monthly a
        LEFT JOIN airport_monthly b
          ON a.airport = b.airport AND a.year = b.year + 1 AND a.month = b.month
        ORDER BY a.airport, a.year, a.month
    """).fetchall()
    con.close()

    return {
        "data": [
            {
                "airport": r[0], "year": r[1], "month": r[2],
                "pax": r[3], "prev_year_pax": r[4], "yoy_pct": r[5],
            }
            for r in rows
        ],
    }


@router.get("/passengers/summary")
def passengers_summary():
    """Summary cards: latest month totals, YoY change, dom/int split per airport."""
    con = get_connection()
    rows = con.execute("""
        WITH latest_period AS (
            SELECT max(year) as y, max(month) as m
            FROM airport_monthly
            WHERE (year, month) IN (
                SELECT year, month FROM airport_monthly ORDER BY year DESC, month DESC LIMIT 1
            )
        ),
        latest AS (
            SELECT a.airport, a.year, a.month, a.dom_pax_total, a.int_pax_total, a.pax_total
            FROM airport_monthly a, latest_period lp
            WHERE a.year = lp.y AND a.month = lp.m
        ),
        prev AS (
            SELECT a.airport, a.pax_total
            FROM airport_monthly a, latest_period lp
            WHERE a.year = CASE WHEN lp.m = 1 THEN lp.y - 1 ELSE lp.y END
              AND a.month = CASE WHEN lp.m = 1 THEN 12 ELSE lp.m - 1 END
        ),
        prev_year AS (
            SELECT a.airport, a.pax_total
            FROM airport_monthly a, latest_period lp
            WHERE a.year = lp.y - 1 AND a.month = lp.m
        )
        SELECT l.airport, l.year, l.month,
               l.pax_total, l.dom_pax_total, l.int_pax_total,
               round((l.pax_total - p.pax_total) * 100.0 / nullif(p.pax_total, 0), 1) as mom_pct,
               round((l.pax_total - py.pax_total) * 100.0 / nullif(py.pax_total, 0), 1) as yoy_pct
        FROM latest l
        LEFT JOIN prev p ON l.airport = p.airport
        LEFT JOIN prev_year py ON l.airport = py.airport
        ORDER BY l.pax_total DESC
    """).fetchall()
    con.close()

    return {
        "data": [
            {
                "airport": r[0], "year": r[1], "month": r[2],
                "total_pax": r[3], "dom_pax": r[4], "int_pax": r[5],
                "mom_pct": r[6], "yoy_pct": r[7],
                "colour": CITY_COLOURS.get(r[0], "#888"),
            }
            for r in rows
        ],
    }


@router.get("/routes")
def routes(
    airport: Optional[str] = Query(None, description="Filter to routes involving this airport"),
    limit: int = Query(20, ge=1, le=100),
):
    """Domestic route stats: passengers, load factor, seats per city pair per month.
    Optional airport filter (e.g. MELBOURNE) shows only routes to/from that city."""
    con = get_connection()
    where = "WHERE city1 = ? OR city2 = ?" if airport else ""
    params = [airport.upper(), airport.upper()] if airport else []
    rows = con.execute(f"""
        SELECT city1, city2, year, month,
               passenger_trips, aircraft_trips, load_factor_pct,
               distance_km, seats
        FROM domestic_routes
        {where}
        ORDER BY year DESC, month DESC, passenger_trips DESC
        LIMIT ?
    """, params + [limit]).fetchall()
    con.close()

    return {
        "data": [
            {
                "city1": r[0], "city2": r[1], "year": r[2], "month": r[3],
                "passengers": r[4], "flights": r[5], "load_factor": r[6],
                "distance_km": r[7], "seats": r[8],
            }
            for r in rows
        ],
    }


@router.get("/routes/top")
def routes_top():
    """Top routes by total passengers across all months, with avg load factor."""
    con = get_connection()
    rows = con.execute("""
        SELECT city1, city2,
               sum(passenger_trips) as total_pax,
               round(avg(load_factor_pct), 1) as avg_load_factor,
               sum(aircraft_trips) as total_flights,
               max(distance_km) as distance_km,
               count(*) as months
        FROM domestic_routes
        GROUP BY city1, city2
        ORDER BY total_pax DESC
        LIMIT 20
    """).fetchall()
    con.close()

    return {
        "data": [
            {
                "city1": r[0], "city2": r[1],
                "total_passengers": r[2], "avg_load_factor": r[3],
                "total_flights": r[4], "distance_km": r[5], "months": r[6],
            }
            for r in rows
        ],
    }


@router.get("/routes/yoy")
def routes_yoy():
    """Monthly passengers per Melbourne route, with YoY comparison.
    Returns 2024 and 2025 side by side so frontend can chart + table both years."""
    con = get_connection()
    rows = con.execute("""
        WITH mel_routes AS (
            SELECT city1, city2, year, month, passenger_trips, load_factor_pct, seats
            FROM domestic_routes
            WHERE city1 = 'MELBOURNE' OR city2 = 'MELBOURNE'
        ),
        ranked AS (
            SELECT city1, city2, sum(passenger_trips) as total
            FROM mel_routes GROUP BY city1, city2
            ORDER BY total DESC LIMIT 10
        )
        SELECT m.city1, m.city2, m.year, m.month,
               m.passenger_trips, m.load_factor_pct, m.seats
        FROM mel_routes m
        INNER JOIN ranked r ON m.city1 = r.city1 AND m.city2 = r.city2
        ORDER BY r.total DESC, m.year, m.month
    """).fetchall()
    con.close()

    return {
        "data": [
            {
                "city1": r[0], "city2": r[1], "year": r[2], "month": r[3],
                "passengers": r[4], "load_factor": r[5], "seats": r[6],
            }
            for r in rows
        ],
    }


@router.get("/otp")
def otp(
    airport: Optional[str] = Query(None, description="Filter to routes involving this airport"),
):
    """On-time performance per route per month. Includes cancellation rate and on-time %."""
    con = get_connection()
    where = ""
    params = []
    if airport:
        where = "WHERE departing_port = ? OR arriving_port = ?"
        params = [airport.title(), airport.title()]
    rows = con.execute(f"""
        SELECT route, departing_port, arriving_port, year, month,
               sectors_scheduled, sectors_flown, cancellations,
               departures_on_time, arrivals_on_time,
               departures_delayed, arrivals_delayed,
               round(cancellations * 100.0 / nullif(sectors_scheduled, 0), 1) as cancel_pct,
               round(arrivals_on_time * 100.0 / nullif(sectors_flown, 0), 1) as ontime_pct
        FROM aviation_otp
        {where}
        ORDER BY year DESC, month DESC, sectors_scheduled DESC
    """, params).fetchall()
    con.close()

    return {
        "data": [
            {
                "route": r[0], "from": r[1], "to": r[2],
                "year": r[3], "month": r[4],
                "scheduled": r[5], "flown": r[6], "cancellations": r[7],
                "dep_ontime": r[8], "arr_ontime": r[9],
                "dep_delayed": r[10], "arr_delayed": r[11],
                "cancel_pct": r[12], "ontime_pct": r[13],
            }
            for r in rows
        ],
    }


@router.get("/otp/summary")
def otp_summary():
    """OTP leaderboard: routes ranked by on-time arrival % (all months aggregated)."""
    con = get_connection()
    rows = con.execute("""
        SELECT route, departing_port, arriving_port,
               sum(sectors_scheduled) as total_sched,
               sum(sectors_flown) as total_flown,
               sum(cancellations) as total_cancel,
               sum(arrivals_on_time) as total_ontime,
               sum(arrivals_delayed) as total_delayed,
               round(sum(cancellations) * 100.0 / nullif(sum(sectors_scheduled), 0), 1) as cancel_pct,
               round(sum(arrivals_on_time) * 100.0 / nullif(sum(sectors_flown), 0), 1) as ontime_pct
        FROM aviation_otp
        GROUP BY route, departing_port, arriving_port
        HAVING sum(sectors_scheduled) > 50
        ORDER BY ontime_pct DESC
    """).fetchall()
    con.close()

    return {
        "data": [
            {
                "route": r[0], "from": r[1], "to": r[2],
                "total_scheduled": r[3], "total_flown": r[4],
                "total_cancellations": r[5], "total_ontime": r[6],
                "total_delayed": r[7],
                "cancel_pct": r[8], "ontime_pct": r[9],
            }
            for r in rows
        ],
    }


@router.get("/otp/yoy")
def otp_yoy():
    """Monthly on-time performance per Melbourne route, with YoY comparison.
    Returns on-time %, cancellation %, and sector counts for 2024 vs 2025."""
    con = get_connection()
    rows = con.execute("""
        WITH mel_routes AS (
            SELECT route, departing_port, arriving_port, year, month,
                   sectors_scheduled, sectors_flown, cancellations,
                   arrivals_on_time, arrivals_delayed,
                   round(arrivals_on_time * 100.0 / nullif(sectors_flown, 0), 1) as ontime_pct,
                   round(cancellations * 100.0 / nullif(sectors_scheduled, 0), 1) as cancel_pct
            FROM aviation_otp
            WHERE departing_port = 'Melbourne' OR arriving_port = 'Melbourne'
        ),
        ranked AS (
            SELECT route, sum(sectors_scheduled) as total
            FROM mel_routes GROUP BY route
            ORDER BY total DESC LIMIT 10
        )
        SELECT m.route, m.departing_port, m.arriving_port, m.year, m.month,
               m.sectors_scheduled, m.sectors_flown, m.cancellations,
               m.arrivals_on_time, m.ontime_pct, m.cancel_pct
        FROM mel_routes m
        INNER JOIN ranked r ON m.route = r.route
        ORDER BY r.total DESC, m.year, m.month
    """).fetchall()
    con.close()

    return {
        "data": [
            {
                "route": r[0], "from": r[1], "to": r[2],
                "year": r[3], "month": r[4],
                "scheduled": r[5], "flown": r[6], "cancellations": r[7],
                "arrivals_ontime": r[8], "ontime_pct": r[9], "cancel_pct": r[10],
            }
            for r in rows
        ],
    }


@router.get("/international")
def international():
    """Monthly international vs domestic passengers per airport, with YoY comparison.
    Returns dom/int split for stacked chart + international YoY table."""
    con = get_connection()
    rows = con.execute("""
        SELECT a.airport, a.year, a.month,
               a.dom_pax_total, a.int_pax_total, a.pax_total,
               round(a.int_pax_total * 100.0 / nullif(a.pax_total, 0), 1) as int_pct,
               b.int_pax_total as prev_year_int,
               round((a.int_pax_total - b.int_pax_total) * 100.0
                     / nullif(b.int_pax_total, 0), 1) as int_yoy_pct
        FROM airport_monthly a
        LEFT JOIN airport_monthly b
          ON a.airport = b.airport AND a.year = b.year + 1 AND a.month = b.month
        ORDER BY a.airport, a.year, a.month
    """).fetchall()
    con.close()

    return {
        "data": [
            {
                "airport": r[0], "year": r[1], "month": r[2],
                "dom_pax": r[3], "int_pax": r[4], "total_pax": r[5],
                "int_pct": r[6], "prev_year_int": r[7], "int_yoy_pct": r[8],
            }
            for r in rows
        ],
        "colours": CITY_COLOURS,
    }
