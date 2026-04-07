"""
Traffic data endpoints — hourly profiles, weekly trends, daily counts.

Victoria only. Weekly trend uses metro core stations (P75+ daily volume).
"""

from fastapi import APIRouter, Query
from typing import Optional
from datetime import date, timedelta
from api.db import get_connection, get_metro_core_count, ARCHIVE_DIR

router = APIRouter()

VIC_FILTER = "h.state = 'VIC'"


def _weeks_ago(weeks: int) -> str:
    """Return ISO date string for N weeks before today. Used to avoid
    f-string interpolation inside SQL INTERVAL expressions."""
    return (date.today() - timedelta(weeks=weeks)).isoformat()


@router.get("/hourly-profile")
def hourly_profile(year: int = Query(2025)):
    """Weekday hourly average vehicles per station for a given year. Returns 24 data points (hours 0-23)."""
    con = get_connection()
    rows = con.execute("""
        SELECT hour_of_day,
               avg(avg_count)::int as avg_count,
               avg(stations)::int as stations
        FROM hourly_city_summary
        WHERE is_weekday = true AND year = ?
        GROUP BY hour_of_day
        ORDER BY hour_of_day
    """, [year]).fetchall()
    con.close()
    return {
        "city": "melbourne",
        "year": year,
        "data": [{"hour": r[0], "avg_count": r[1], "stations": r[2]} for r in rows],
    }


@router.get("/hourly-profile-multi")
def hourly_profile_multi(
    years: str = Query("2024,2025,2026"),
    day_type: str = Query("weekday"),
):
    """Hourly profiles for multiple years. day_type: weekday | saturday | sunday."""
    con = get_connection()
    year_list = [int(y.strip()) for y in years.split(",")]

    if day_type == "saturday":
        day_filter = "day_of_week = 6"
    elif day_type == "sunday":
        day_filter = "day_of_week = 7"
    else:
        day_filter = "is_weekday = true"

    result = {}
    for year in year_list:
        rows = con.execute(f"""
            SELECT hour_of_day, avg(avg_count)::int as avg_count
            FROM hourly_city_summary
            WHERE {day_filter} AND year = ?
            GROUP BY hour_of_day ORDER BY hour_of_day
        """, [year]).fetchall()
        result[str(year)] = [{"hour": r[0], "avg_count": r[1]} for r in rows]
    con.close()
    return {"city": "melbourne", "years": year_list, "day_type": day_type, "data": result}


@router.get("/weekly-trend")
def weekly_trend(weeks: int = Query(26, ge=4, le=104)):
    """Weekly weekday average vehicles per station, most recent N weeks.
    Metro core stations only. Includes YoY comparison data."""
    con = get_connection()
    core_count = get_metro_core_count(con)
    rows = con.execute("""
        SELECT date_trunc('week', day)::DATE as week,
               sum(daily_total)::bigint
                   / count(DISTINCT day)
                   / count(DISTINCT station_id) as avg_per_station,
               count(DISTINCT day) as weekdays,
               count(DISTINCT station_id) as stations
        FROM daily_station_summary
        WHERE is_weekday = true
        GROUP BY 1
        HAVING count(DISTINCT day) >= 3
        ORDER BY 1 DESC
        LIMIT ?
    """, [weeks]).fetchall()
    data = [{"week": str(r[0]), "avg_per_station": int(r[1]),
             "weekdays": r[2], "stations": r[3]} for r in reversed(rows)]

    # YoY comparison: same calendar weeks, one year prior
    if data:
        earliest = data[0]["week"]
        latest = data[-1]["week"]
        yoy_rows = con.execute(f"""
            SELECT date_trunc('week', day)::DATE as week,
                   sum(daily_total)::bigint
                       / count(DISTINCT day)
                       / count(DISTINCT station_id) as avg_per_station,
                   count(DISTINCT day) as weekdays,
                   count(DISTINCT station_id) as stations
            FROM daily_station_summary
            WHERE is_weekday = true
              AND day >= (DATE '{earliest}' - INTERVAL '1 year')
              AND day < (DATE '{latest}' - INTERVAL '1 year' + INTERVAL '8 days')
            GROUP BY 1
            HAVING count(DISTINCT day) >= 3
            ORDER BY 1
        """).fetchall()
        yoy_data = [{"week": str(r[0]), "avg_per_station": int(r[1]),
                      "weekdays": r[2], "stations": r[3]} for r in yoy_rows]
    else:
        yoy_data = []

    con.close()
    return {"city": "melbourne", "weeks": len(data), "metro_core_stations": core_count,
            "data": data, "yoy_data": yoy_data}


@router.get("/daily-counts")
def daily_counts(
    date_from: str = Query(None),
    date_to: str = Query(None),
):
    """Daily total and per-station average with calendar context. Metro core stations only."""
    # Default to rolling 8-week window ending today
    if not date_to:
        date_to = date.today().isoformat()
    if not date_from:
        date_from = (date.today() - timedelta(weeks=8)).isoformat()
    con = get_connection()
    rows = con.execute("""
        SELECT d.day,
               sum(d.daily_total)::bigint as daily_total,
               sum(d.daily_total)::bigint / count(DISTINCT d.station_id) as avg_per_station,
               count(DISTINCT d.station_id) as stations,
               c.day_of_week,
               c.is_weekday,
               c.is_public_holiday_vic as is_holiday
        FROM daily_station_summary d
        JOIN calendar c ON d.day = c.date
        WHERE d.day BETWEEN ?::DATE AND ?::DATE
        GROUP BY d.day, c.day_of_week, c.is_weekday, c.is_public_holiday_vic
        ORDER BY 1
    """, [date_from, date_to]).fetchall()
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
    rows = con.execute("""
        SELECT day_of_week, avg(avg_count)::int as avg_count
        FROM hourly_city_summary
        WHERE hour_of_day BETWEEN 7 AND 18
          AND year = ?
        GROUP BY day_of_week ORDER BY day_of_week
    """, [year]).fetchall()
    con.close()
    day_names = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}
    data = [{"day_num": r[0], "day": day_names.get(r[0], "?"), "avg_count": r[1]} for r in rows]
    return {"city": "melbourne", "year": year, "data": data}


@router.get("/heatmap")
def heatmap(weeks: int = Query(12, ge=4, le=52)):
    """Hour-of-day x day-of-week heatmap. Returns 7x24 grid of avg vehicle counts per station."""
    con = get_connection()
    rows = con.execute("""
        SELECT day_of_week, hour_of_day,
               avg(avg_count)::int as avg_count
        FROM hourly_city_summary
        WHERE day >= ?::DATE
        GROUP BY day_of_week, hour_of_day
        ORDER BY day_of_week, hour_of_day
    """, [_weeks_ago(weeks)]).fetchall()
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
        FROM read_parquet(?)
        WHERE station_id = ? AND is_weekday = true
        GROUP BY hour_of_day ORDER BY hour_of_day
    """, [str(ARCHIVE_DIR / f"hourly_counts_{year}.parquet"), station_id]).fetchall()
    con.close()
    return {
        "station": {"id": meta[0], "road_name": meta[1], "suburb": meta[2],
                     "road_type": meta[3], "lat": meta[4], "lon": meta[5]},
        "year": year,
        "hourly": [{"hour": r[0], "avg_count": r[1], "samples": r[2]} for r in rows],
    }


@router.get("/month-on-month")
def month_on_month():
    """Monthly average weekday traffic per station with YoY % change. Metro core stations only."""
    con = get_connection()
    rows = con.execute("""
        SELECT date_trunc('month', day)::DATE as month,
               (AVG(daily_total))::int as avg_per_station,
               count(DISTINCT station_id) as stations,
               count(DISTINCT day) as days_reporting
        FROM daily_station_summary
        WHERE is_weekday = true
        GROUP BY 1 ORDER BY 1
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
    """Compare average weekday traffic during school holidays vs term time. Metro core stations only."""
    con = get_connection()
    rows = con.execute("""
        SELECT c.is_school_holiday_vic as is_school_holiday,
               date_trunc('month', d.day)::DATE as month,
               (AVG(d.daily_total))::int as avg_per_station,
               count(DISTINCT d.day) as days_reporting
        FROM daily_station_summary d
        JOIN calendar c ON d.day = c.date
        WHERE d.is_weekday = true
          AND d.day >= CURRENT_DATE - INTERVAL '12 months'
        GROUP BY 1, 2 ORDER BY 2, 1
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
    date_from: str = Query(None),
    date_to: str = Query(None),
):
    """Public holidays, school holiday periods, and major events for chart annotations."""
    if not date_from:
        date_from = (date.today() - timedelta(days=365)).isoformat()
    if not date_to:
        date_to = (date.today() + timedelta(days=180)).isoformat()
    con = get_connection()
    holidays = con.execute("""
        SELECT date, event_name FROM calendar
        WHERE is_public_holiday_vic = true AND date BETWEEN ?::DATE AND ?::DATE
        ORDER BY date
    """, [date_from, date_to]).fetchall()
    school_days = con.execute("""
        SELECT date FROM calendar
        WHERE is_school_holiday_vic = true AND date BETWEEN ?::DATE AND ?::DATE
        ORDER BY date
    """, [date_from, date_to]).fetchall()
    school_ranges = []
    if school_days:
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
    events = con.execute("""
        SELECT date, event_name FROM calendar
        WHERE event_name IS NOT NULL AND date BETWEEN ?::DATE AND ?::DATE
        ORDER BY date
    """, [date_from, date_to]).fetchall()
    con.close()
    return {
        "city": "melbourne",
        "public_holidays": [{"date": str(h[0]), "name": h[1] or "Public holiday"} for h in holidays],
        "school_holidays": school_ranges,
        "events": [{"date": str(e[0]), "name": e[1]} for e in events],
    }


@router.get("/peak-days")
def peak_days(top_n: int = Query(20)):
    """
    Rank the busiest and quietest weekdays across metro core stations.
    Returns top N busiest + top N quietest, annotated with calendar context.
    """
    con = get_connection()
    rows = con.execute("""
        WITH daily AS (
            SELECT d.day,
                   (SUM(d.daily_total)::DOUBLE / COUNT(DISTINCT d.station_id))::INT as avg_per_station
            FROM daily_station_summary d
            GROUP BY 1
        )
        SELECT d.day, d.avg_per_station,
               DAYNAME(d.day) as dow,
               c.is_weekday,
               c.is_public_holiday_vic,
               c.is_school_holiday_vic,
               c.event_name
        FROM daily d
        LEFT JOIN calendar c ON d.day = c.date
        WHERE c.is_weekday = true
        ORDER BY d.avg_per_station DESC
    """).fetchall()
    con.close()

    def to_dict(r):
        context = []
        if r[4]: context.append('public holiday')
        if r[5]: context.append('school holiday')
        if r[6]: context.append(r[6])
        return {
            "date": str(r[0]),
            "dow": r[2],
            "avg_per_station": r[1],
            "context": ', '.join(context) if context else None,
        }

    busiest = [to_dict(r) for r in rows[:top_n]]
    quietest = [to_dict(r) for r in rows[-top_n:]]
    quietest.reverse()

    return {
        "city": "melbourne",
        "busiest": busiest,
        "quietest": quietest,
    }


@router.get("/event-impact")
def event_impact():
    """
    Compare traffic around named calendar events vs a 4-week baseline.
    For each event: avg traffic on the event day + surrounding 2 days,
    vs avg of the same day-of-week over the 4 weeks before/after.

    Single-pass: computes daily averages once, then filters per event in Python.
    """
    con = get_connection()

    # 1. All named events
    events = con.execute("""
        SELECT date, event_name FROM calendar
        WHERE event_name IS NOT NULL
          AND date >= '2024-01-01' AND date <= CURRENT_DATE
        ORDER BY date
    """).fetchall()

    # 2. Daily avg per station — from summary table, not raw hourly_counts
    daily_rows = con.execute("""
        SELECT day,
               (SUM(daily_total)::DOUBLE / COUNT(DISTINCT station_id))::INT as avg_per_station
        FROM daily_station_summary
        WHERE day >= '2023-12-01'
        GROUP BY 1
    """).fetchall()
    con.close()

    # Index by date for fast lookup
    from datetime import timedelta
    daily = {r[0]: {"avg": r[1], "dow": r[0].isoweekday()} for r in daily_rows}

    results = []
    for ev_date, ev_name in events:
        ev_dow = ev_date.isoweekday()

        # Event window: event day ± 1 day
        event_vals = []
        for offset in range(-1, 2):
            d = ev_date + timedelta(days=offset)
            if d in daily:
                event_vals.append(daily[d]["avg"])

        # Baseline: same day-of-week, 1-5 weeks before and after (excluding event week)
        baseline_vals = []
        for week_offset in range(1, 6):
            for direction in (-1, 1):
                d = ev_date + timedelta(weeks=week_offset * direction)
                if d in daily and daily[d]["dow"] == ev_dow:
                    baseline_vals.append(daily[d]["avg"])

        event_avg = int(sum(event_vals) / len(event_vals)) if event_vals else None
        baseline_avg = int(sum(baseline_vals) / len(baseline_vals)) if baseline_vals else None

        if event_avg and baseline_avg:
            pct = round((event_avg - baseline_avg) / baseline_avg * 100, 1)
        else:
            pct = None

        results.append({
            "date": str(ev_date),
            "event": ev_name,
            "event_avg": event_avg,
            "baseline_avg": baseline_avg,
            "impact_pct": pct,
        })

    return {"city": "melbourne", "events": results}


@router.get("/weekday-drift")
def weekday_drift():
    """
    Compare the day-of-week traffic profile across 2024, 2025, and 2026.
    Like-for-like: all years filtered to the same Jan 1 → latest-2026-date
    window so seasonal mix is identical. Business hours (7am-6pm) only,
    metro core stations, public holidays excluded.
    """
    con = get_connection()

    # Find the latest date in 2026 to set the comparison window
    cutoff = con.execute("""
        SELECT MAX(day) FROM daily_station_summary WHERE year = 2026
    """).fetchone()[0]
    if not cutoff:
        con.close()
        return {"city": "melbourne", "data": [], "note": "No 2026 data available"}

    # Month-day cutoff for like-for-like comparison across years
    cutoff_md = cutoff.strftime('%m-%d')

    rows = con.execute("""
        WITH daily AS (
            SELECT d.day,
                   d.day_of_week as dow,
                   d.year as yr,
                   (SUM(d.biz_hours_total)::DOUBLE / COUNT(DISTINCT d.station_id))::INT as avg_per_station
            FROM daily_station_summary d
            JOIN calendar c ON d.day = c.date
            WHERE d.is_weekday = true
              AND c.is_public_holiday_vic = false
              AND d.year IN (2024, 2025, 2026)
              AND STRFTIME(d.day, '%m-%d') <= ?
            GROUP BY 1, 2, 3
        )
        SELECT yr, dow, AVG(avg_per_station)::INT as avg_traffic,
               COUNT(DISTINCT day) as days_sampled
        FROM daily
        GROUP BY yr, dow
        ORDER BY yr, dow
    """, [cutoff_md]).fetchall()
    con.close()

    DOW_NAMES = ['', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri']
    by_year = {2024: {}, 2025: {}, 2026: {}}
    for r in rows:
        yr, dow, avg, days = r
        if yr in by_year:
            by_year[yr][dow] = {"avg": avg, "days": days}

    combined = []
    for dow in range(1, 6):
        avg_24 = by_year[2024].get(dow, {}).get('avg', 0)
        avg_25 = by_year[2025].get(dow, {}).get('avg', 0)
        avg_26 = by_year[2026].get(dow, {}).get('avg', 0)
        pct_24_25 = round((avg_25 - avg_24) / avg_24 * 100, 1) if avg_24 else None
        pct_25_26 = round((avg_26 - avg_25) / avg_25 * 100, 1) if avg_25 else None
        combined.append({
            "day": DOW_NAMES[dow],
            "avg_2024": avg_24,
            "avg_2025": avg_25,
            "avg_2026": avg_26,
            "change_pct_24_25": pct_24_25,
            "change_pct_25_26": pct_25_26,
        })

    days_sampled = {yr: sum(by_year[yr].get(dow, {}).get('days', 0) for dow in range(1, 6)) for yr in [2024, 2025, 2026]}
    return {
        "city": "melbourne",
        "data": combined,
        "comparison_window": f"1 Jan – {cutoff.strftime('%-d %b')} each year",
        "days_sampled": days_sampled,
    }
