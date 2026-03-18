"""
Traffic data endpoints — hourly profiles, weekly trends, daily counts.

Victoria only. All queries use the full SCATS network (~3,860 stations).
"""

from fastapi import APIRouter, Query
from typing import Optional
from api.db import get_connection

router = APIRouter()

VIC_FILTER = "h.state = 'VIC'"


@router.get("/hourly-profile")
def hourly_profile(year: int = Query(2025)):
    """Weekday hourly average vehicles per station for a given year. Returns 24 data points (hours 0-23)."""
    con = get_connection()
    rows = con.execute(f"""
        SELECT hour_of_day,
               avg(vehicle_count)::int as avg_count,
               count(DISTINCT station_id) as stations
        FROM hourly_counts h
        WHERE {VIC_FILTER}
          AND is_weekday = true
          AND ts_hour >= '{year}-01-01'
          AND ts_hour < '{year + 1}-01-01'
        GROUP BY hour_of_day
        ORDER BY hour_of_day
    """).fetchall()
    con.close()
    return {
        "city": "melbourne",
        "year": year,
        "data": [{"hour": r[0], "avg_count": r[1], "stations": r[2]} for r in rows],
    }


@router.get("/hourly-profile-multi")
def hourly_profile_multi(years: str = Query("2024,2025,2026")):
    """Weekday hourly profiles for multiple years, for overlay comparison."""
    con = get_connection()
    year_list = [int(y.strip()) for y in years.split(",")]
    result = {}
    for year in year_list:
        rows = con.execute(f"""
            SELECT hour_of_day, avg(vehicle_count)::int as avg_count
            FROM hourly_counts h
            WHERE {VIC_FILTER} AND is_weekday = true
              AND ts_hour >= ?::TIMESTAMP AND ts_hour < ?::TIMESTAMP
            GROUP BY hour_of_day ORDER BY hour_of_day
        """, [f"{year}-01-01", f"{year + 1}-01-01"]).fetchall()
        result[str(year)] = [{"hour": r[0], "avg_count": r[1]} for r in rows]
    con.close()
    return {"city": "melbourne", "years": year_list, "data": result}


@router.get("/weekly-trend")
def weekly_trend(weeks: int = Query(26, ge=4, le=104)):
    """Weekly weekday average vehicles per station, most recent N weeks."""
    con = get_connection()
    rows = con.execute(f"""
        SELECT date_trunc('week', CAST(ts_hour AS DATE))::DATE as week,
               sum(vehicle_count)::bigint
                   / count(DISTINCT CAST(ts_hour AS DATE))
                   / count(DISTINCT station_id) as avg_per_station,
               count(DISTINCT CAST(ts_hour AS DATE)) as weekdays,
               count(DISTINCT station_id) as stations
        FROM hourly_counts h
        WHERE {VIC_FILTER}
          AND ISODOW(CAST(ts_hour AS DATE)) <= 5
        GROUP BY 1
        HAVING count(DISTINCT CAST(ts_hour AS DATE)) >= 3
        ORDER BY 1 DESC
        LIMIT {weeks}
    """).fetchall()
    con.close()
    data = [{"week": str(r[0]), "avg_per_station": int(r[1]),
             "weekdays": r[2], "stations": r[3]} for r in reversed(rows)]
    return {"city": "melbourne", "weeks": len(data), "data": data}


@router.get("/daily-counts")
def daily_counts(
    date_from: str = Query("2026-02-01"),
    date_to: str = Query("2026-03-31"),
):
    """Daily total and per-station average with calendar context."""
    con = get_connection()
    rows = con.execute(f"""
        SELECT CAST(h.ts_hour AS DATE) as day,
               sum(h.vehicle_count)::bigint as daily_total,
               sum(h.vehicle_count)::bigint / count(DISTINCT h.station_id) as avg_per_station,
               count(DISTINCT h.station_id) as stations,
               c.day_of_week,
               c.is_weekday,
               c.is_public_holiday_vic as is_holiday
        FROM hourly_counts h
        JOIN calendar c ON CAST(h.ts_hour AS DATE) = c.date
        WHERE {VIC_FILTER}
          AND CAST(h.ts_hour AS DATE) BETWEEN '{date_from}' AND '{date_to}'
        GROUP BY 1, c.day_of_week, c.is_weekday, c.is_public_holiday_vic
        ORDER BY 1
    """).fetchall()
    con.close()
    data = [{
        "day": str(r[0]), "daily_total": int(r[1]), "avg_per_station": int(r[2]),
        "stations": int(r[3]), "day_of_week": int(r[4]),
        "is_weekday": bool(r[5]), "is_holiday": bool(r[6]),
    } for r in rows]
    return {"city": "melbourne", "date_from": date_from, "date_to": date_to, "data": data}


@router.get("/day-of-week")
def day_of_week(year: int = Query(2025)):
    """Day-of-week average (Mon-Sun) for a given year. Business hours (7am-6pm)."""
    con = get_connection()
    rows = con.execute(f"""
        SELECT day_of_week, avg(vehicle_count)::int as avg_count
        FROM hourly_counts h
        WHERE {VIC_FILTER}
          AND hour_of_day BETWEEN 7 AND 18
          AND ts_hour >= ?::TIMESTAMP AND ts_hour < ?::TIMESTAMP
        GROUP BY day_of_week ORDER BY day_of_week
    """, [f"{year}-01-01", f"{year + 1}-01-01"]).fetchall()
    con.close()
    day_names = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}
    data = [{"day_num": r[0], "day": day_names.get(r[0], "?"), "avg_count": r[1]} for r in rows]
    return {"city": "melbourne", "year": year, "data": data}


@router.get("/heatmap")
def heatmap(weeks: int = Query(12, ge=4, le=52)):
    """Hour-of-day x day-of-week heatmap. Returns 7x24 grid of avg vehicle counts per station."""
    con = get_connection()
    rows = con.execute(f"""
        SELECT day_of_week, hour_of_day,
               avg(vehicle_count)::int as avg_count
        FROM hourly_counts h
        WHERE {VIC_FILTER}
          AND ts_hour >= CURRENT_DATE - INTERVAL '{weeks} weeks'
        GROUP BY day_of_week, hour_of_day
        ORDER BY day_of_week, hour_of_day
    """).fetchall()
    con.close()
    day_names = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}
    data = [{"day_num": r[0], "day": day_names.get(r[0], "?"),
             "hour": r[1], "avg_count": r[2]} for r in rows]
    return {"city": "melbourne", "weeks": weeks, "data": data}


@router.get("/station-profile")
def station_profile(station_id: str = Query(...), year: int = Query(2025)):
    """Hourly weekday profile for a single station with metadata."""
    con = get_connection()
    meta = con.execute("""
        SELECT station_id, road_name, suburb, road_type, latitude, longitude
        FROM stations WHERE station_id = ?
    """, [station_id]).fetchone()
    if not meta:
        con.close()
        return {"error": f"Station {station_id} not found"}
    rows = con.execute("""
        SELECT hour_of_day, avg(vehicle_count)::int as avg_count, count(*) as sample_hours
        FROM hourly_counts
        WHERE station_id = ? AND is_weekday = true
          AND ts_hour >= ?::TIMESTAMP AND ts_hour < ?::TIMESTAMP
        GROUP BY hour_of_day ORDER BY hour_of_day
    """, [station_id, f"{year}-01-01", f"{year + 1}-01-01"]).fetchall()
    con.close()
    return {
        "station": {"id": meta[0], "road_name": meta[1], "suburb": meta[2],
                     "road_type": meta[3], "lat": meta[4], "lon": meta[5]},
        "year": year,
        "hourly": [{"hour": r[0], "avg_count": r[1], "samples": r[2]} for r in rows],
    }


@router.get("/month-on-month")
def month_on_month():
    """Monthly average weekday traffic per station with YoY % change."""
    con = get_connection()
    rows = con.execute(f"""
        WITH daily AS (
            SELECT station_id, CAST(ts_hour AS DATE) as day,
                   SUM(vehicle_count) as daily_total
            FROM hourly_counts h
            WHERE {VIC_FILTER} AND ISODOW(CAST(ts_hour AS DATE)) <= 5
            GROUP BY 1, 2
        )
        SELECT date_trunc('month', day)::DATE as month,
               (AVG(daily_total))::int as avg_per_station,
               count(DISTINCT station_id) as stations,
               count(DISTINCT day) as days_reporting
        FROM daily GROUP BY 1 ORDER BY 1
    """).fetchall()
    con.close()
    by_month = {}
    for r in rows:
        by_month[(r[0].year, r[0].month)] = {"month": str(r[0]), "avg": r[1], "stations": r[2], "days": r[3]}
    data = []
    for r in rows:
        entry = {"month": str(r[0]), "avg": r[1], "stations": r[2], "days": r[3]}
        yoy_key = (r[0].year - 1, r[0].month)
        if yoy_key in by_month:
            yoy_avg = by_month[yoy_key]["avg"]
            entry["yoy_avg"] = yoy_avg
            entry["yoy_pct"] = round((r[1] - yoy_avg) / yoy_avg * 100, 1) if yoy_avg else None
        else:
            entry["yoy_avg"] = None
            entry["yoy_pct"] = None
        data.append(entry)
    return {"city": "melbourne", "data": data}


@router.get("/school-holiday-effect")
def school_holiday_effect():
    """Compare average weekday traffic during school holidays vs term time."""
    con = get_connection()
    rows = con.execute(f"""
        WITH daily AS (
            SELECT h.station_id, CAST(h.ts_hour AS DATE) as day,
                   c.is_school_holiday_vic as is_school_holiday,
                   SUM(h.vehicle_count) as daily_total
            FROM hourly_counts h
            JOIN calendar c ON CAST(h.ts_hour AS DATE) = c.date
            WHERE {VIC_FILTER} AND c.is_weekday = true
              AND h.ts_hour >= CURRENT_DATE - INTERVAL '12 months'
            GROUP BY 1, 2, 3
        )
        SELECT is_school_holiday,
               date_trunc('month', day)::DATE as month,
               (AVG(daily_total))::int as avg_per_station,
               count(DISTINCT day) as days_reporting
        FROM daily GROUP BY 1, 2 ORDER BY 2, 1
    """).fetchall()
    con.close()
    term_rows = [r for r in rows if not r[0]]
    hol_rows = [r for r in rows if r[0]]
    term_avg = sum(r[2] for r in term_rows) // len(term_rows) if term_rows else 0
    hol_avg = sum(r[2] for r in hol_rows) // len(hol_rows) if hol_rows else 0
    effect_pct = round((hol_avg - term_avg) / term_avg * 100, 1) if term_avg else 0
    monthly = {}
    for r in rows:
        m = str(r[1])
        if m not in monthly:
            monthly[m] = {}
        key = "holiday" if r[0] else "term"
        monthly[m][key] = {"avg": r[2], "days": r[3]}
    data = []
    for m in sorted(monthly.keys()):
        entry = {"month": m}
        entry["term"] = monthly[m].get("term", {}).get("avg")
        entry["holiday"] = monthly[m].get("holiday", {}).get("avg")
        if entry["term"] and entry["holiday"]:
            entry["effect_pct"] = round((entry["holiday"] - entry["term"]) / entry["term"] * 100, 1)
        else:
            entry["effect_pct"] = None
        data.append(entry)
    return {"city": "melbourne", "summary": {"term_avg": term_avg, "holiday_avg": hol_avg, "effect_pct": effect_pct}, "monthly": data}


@router.get("/calendar-events")
def calendar_events(
    date_from: str = Query("2025-03-01"),
    date_to: str = Query("2026-03-31"),
):
    """Public holidays, school holiday periods, and major events for chart annotations."""
    con = get_connection()
    holidays = con.execute(f"""
        SELECT date, event_name FROM calendar
        WHERE is_public_holiday_vic = true AND date BETWEEN '{date_from}' AND '{date_to}'
        ORDER BY date
    """).fetchall()
    school_days = con.execute(f"""
        SELECT date FROM calendar
        WHERE is_school_holiday_vic = true AND date BETWEEN '{date_from}' AND '{date_to}'
        ORDER BY date
    """).fetchall()
    school_ranges = []
    if school_days:
        from datetime import timedelta
        current_start = school_days[0][0]
        current_end = school_days[0][0]
        for row in school_days[1:]:
            d = row[0]
            if (d - current_end).days <= 1:
                current_end = d
            else:
                school_ranges.append({"start": str(current_start), "end": str(current_end)})
                current_start = d
                current_end = d
        school_ranges.append({"start": str(current_start), "end": str(current_end)})
    events = con.execute(f"""
        SELECT date, event_name FROM calendar
        WHERE event_name IS NOT NULL AND date BETWEEN '{date_from}' AND '{date_to}'
        ORDER BY date
    """).fetchall()
    con.close()
    return {
        "city": "melbourne",
        "public_holidays": [{"date": str(h[0]), "name": h[1] or "Public holiday"} for h in holidays],
        "school_holidays": school_ranges,
        "events": [{"date": str(e[0]), "name": e[1]} for e in events],
    }
