"""
Traffic data endpoints — hourly profiles, weekly trends, daily counts.

Victoria only. Weekly trend uses metro core stations (P75+ daily volume).
"""

from fastapi import APIRouter, Query
from typing import Optional
from api.db import get_connection, create_metro_core_table

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
def hourly_profile_multi(
    years: str = Query("2024,2025,2026"),
    day_type: str = Query("weekday"),
):
    """Hourly profiles for multiple years. day_type: weekday | saturday | sunday."""
    con = get_connection()
    year_list = [int(y.strip()) for y in years.split(",")]

    if day_type == "saturday":
        day_filter = "ISODOW(CAST(h.ts_hour AS DATE)) = 6"
    elif day_type == "sunday":
        day_filter = "ISODOW(CAST(h.ts_hour AS DATE)) = 7"
    else:
        day_filter = "is_weekday = true"

    result = {}
    for year in year_list:
        rows = con.execute(f"""
            SELECT hour_of_day, avg(vehicle_count)::int as avg_count
            FROM hourly_counts h
            WHERE {VIC_FILTER} AND {day_filter}
              AND ts_hour >= ?::TIMESTAMP AND ts_hour < ?::TIMESTAMP
            GROUP BY hour_of_day ORDER BY hour_of_day
        """, [f"{year}-01-01", f"{year + 1}-01-01"]).fetchall()
        result[str(year)] = [{"hour": r[0], "avg_count": r[1]} for r in rows]
    con.close()
    return {"city": "melbourne", "years": year_list, "day_type": day_type, "data": result}


@router.get("/weekly-trend")
def weekly_trend(weeks: int = Query(26, ge=4, le=104)):
    """Weekly weekday average vehicles per station, most recent N weeks.
    Metro core stations only. Includes YoY comparison data."""
    con = get_connection()
    core_count = create_metro_core_table(con)
    rows = con.execute(f"""
        SELECT date_trunc('week', CAST(ts_hour AS DATE))::DATE as week,
               sum(vehicle_count)::bigint
                   / count(DISTINCT CAST(ts_hour AS DATE))
                   / count(DISTINCT h.station_id) as avg_per_station,
               count(DISTINCT CAST(ts_hour AS DATE)) as weekdays,
               count(DISTINCT h.station_id) as stations
        FROM hourly_counts h
        INNER JOIN metro_core_stations m ON h.station_id = m.station_id
        WHERE {VIC_FILTER}
          AND ISODOW(CAST(ts_hour AS DATE)) <= 5
        GROUP BY 1
        HAVING count(DISTINCT CAST(ts_hour AS DATE)) >= 3
        ORDER BY 1 DESC
        LIMIT {weeks}
    """).fetchall()
    data = [{"week": str(r[0]), "avg_per_station": int(r[1]),
             "weekdays": r[2], "stations": r[3]} for r in reversed(rows)]

    # YoY comparison: same calendar weeks, one year prior
    if data:
        earliest = data[0]["week"]
        latest = data[-1]["week"]
        yoy_rows = con.execute(f"""
            SELECT date_trunc('week', CAST(ts_hour AS DATE))::DATE as week,
                   sum(vehicle_count)::bigint
                       / count(DISTINCT CAST(ts_hour AS DATE))
                       / count(DISTINCT h.station_id) as avg_per_station,
                   count(DISTINCT CAST(ts_hour AS DATE)) as weekdays,
                   count(DISTINCT h.station_id) as stations
            FROM hourly_counts h
            INNER JOIN metro_core_stations m ON h.station_id = m.station_id
            WHERE {VIC_FILTER}
              AND ISODOW(CAST(ts_hour AS DATE)) <= 5
              AND CAST(ts_hour AS DATE) >= (DATE '{earliest}' - INTERVAL '1 year')
              AND CAST(ts_hour AS DATE) < (DATE '{latest}' - INTERVAL '1 year' + INTERVAL '8 days')
            GROUP BY 1
            HAVING count(DISTINCT CAST(ts_hour AS DATE)) >= 3
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
    date_from: str = Query("2026-02-01"),
    date_to: str = Query("2026-03-31"),
):
    """Daily total and per-station average with calendar context. Metro core stations only."""
    con = get_connection()
    create_metro_core_table(con)
    rows = con.execute(f"""
        SELECT CAST(h.ts_hour AS DATE) as day,
               sum(h.vehicle_count)::bigint as daily_total,
               sum(h.vehicle_count)::bigint / count(DISTINCT h.station_id) as avg_per_station,
               count(DISTINCT h.station_id) as stations,
               c.day_of_week,
               c.is_weekday,
               c.is_public_holiday_vic as is_holiday
        FROM hourly_counts h
        INNER JOIN metro_core_stations m ON h.station_id = m.station_id
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
    """Monthly average weekday traffic per station with YoY % change. Metro core stations only."""
    con = get_connection()
    create_metro_core_table(con)
    rows = con.execute(f"""
        WITH daily AS (
            SELECT h.station_id, CAST(h.ts_hour AS DATE) as day,
                   SUM(h.vehicle_count) as daily_total
            FROM hourly_counts h
            INNER JOIN metro_core_stations m ON h.station_id = m.station_id
            WHERE {VIC_FILTER} AND ISODOW(CAST(h.ts_hour AS DATE)) <= 5
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
    """Compare average weekday traffic during school holidays vs term time. Metro core stations only."""
    con = get_connection()
    create_metro_core_table(con)
    rows = con.execute(f"""
        WITH daily AS (
            SELECT h.station_id, CAST(h.ts_hour AS DATE) as day,
                   c.is_school_holiday_vic as is_school_holiday,
                   SUM(h.vehicle_count) as daily_total
            FROM hourly_counts h
            INNER JOIN metro_core_stations m ON h.station_id = m.station_id
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


@router.get("/peak-days")
def peak_days(top_n: int = Query(20)):
    """
    Rank the busiest and quietest weekdays across metro core stations.
    Returns top N busiest + top N quietest, annotated with calendar context.
    """
    con = get_connection()
    create_metro_core_table(con)
    rows = con.execute(f"""
        WITH daily AS (
            SELECT CAST(h.ts_hour AS DATE) as day,
                   (SUM(h.vehicle_count)::DOUBLE / COUNT(DISTINCT h.station_id))::INT as avg_per_station
            FROM hourly_counts h
            INNER JOIN metro_core_stations m ON h.station_id = m.station_id
            WHERE {VIC_FILTER}
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
    """
    con = get_connection()
    create_metro_core_table(con)

    events = con.execute("""
        SELECT date, event_name FROM calendar
        WHERE event_name IS NOT NULL
          AND date >= '2024-01-01' AND date <= CURRENT_DATE
        ORDER BY date
    """).fetchall()

    results = []
    for ev_date, ev_name in events:
        rows = con.execute(f"""
            WITH daily AS (
                SELECT CAST(h.ts_hour AS DATE) as day,
                       (SUM(h.vehicle_count)::DOUBLE / COUNT(DISTINCT h.station_id))::INT as avg_per_station
                FROM hourly_counts h
                INNER JOIN metro_core_stations m ON h.station_id = m.station_id
                WHERE {VIC_FILTER}
                GROUP BY 1
            ),
            event_window AS (
                SELECT day, avg_per_station, 'event' as period
                FROM daily
                WHERE day BETWEEN ?::DATE - 1 AND ?::DATE + 1
            ),
            baseline_before AS (
                SELECT day, avg_per_station, 'baseline' as period
                FROM daily
                WHERE day BETWEEN ?::DATE - 35 AND ?::DATE - 7
                  AND ISODOW(day) = ISODOW(?::DATE)
            ),
            baseline_after AS (
                SELECT day, avg_per_station, 'baseline' as period
                FROM daily
                WHERE day BETWEEN ?::DATE + 7 AND ?::DATE + 35
                  AND ISODOW(day) = ISODOW(?::DATE)
            )
            SELECT period, AVG(avg_per_station)::INT as avg_val, COUNT(*) as days
            FROM (
                SELECT * FROM event_window
                UNION ALL SELECT * FROM baseline_before
                UNION ALL SELECT * FROM baseline_after
            )
            GROUP BY period
        """, [ev_date, ev_date, ev_date, ev_date, ev_date, ev_date, ev_date, ev_date]).fetchall()

        event_avg = None
        baseline_avg = None
        for r in rows:
            if r[0] == 'event': event_avg = r[1]
            elif r[0] == 'baseline': baseline_avg = r[1]

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
    Compare the day-of-week traffic profile between 2024 and 2025.
    Shows whether Fridays are getting quieter, Mondays shifting, etc.
    Business hours (7am-6pm) only, metro core stations.
    """
    con = get_connection()
    create_metro_core_table(con)
    rows = con.execute(f"""
        WITH daily AS (
            SELECT CAST(h.ts_hour AS DATE) as day,
                   ISODOW(CAST(h.ts_hour AS DATE)) as dow,
                   EXTRACT(YEAR FROM h.ts_hour)::INT as yr,
                   (SUM(h.vehicle_count)::DOUBLE / COUNT(DISTINCT h.station_id))::INT as avg_per_station
            FROM hourly_counts h
            INNER JOIN metro_core_stations m ON h.station_id = m.station_id
            JOIN calendar c ON CAST(h.ts_hour AS DATE) = c.date
            WHERE {VIC_FILTER}
              AND h.hour_of_day BETWEEN 7 AND 17
              AND c.is_weekday = true
              AND c.is_public_holiday_vic = false
              AND EXTRACT(YEAR FROM h.ts_hour) IN (2024, 2025)
            GROUP BY 1, 2, 3
        )
        SELECT yr, dow, AVG(avg_per_station)::INT as avg_traffic,
               COUNT(DISTINCT day) as days_sampled
        FROM daily
        GROUP BY yr, dow
        ORDER BY yr, dow
    """).fetchall()
    con.close()

    DOW_NAMES = ['', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri']
    data_2024 = {}
    data_2025 = {}
    for r in rows:
        entry = {"dow": r[1], "day": DOW_NAMES[r[1]] if r[1] <= 5 else None, "avg": r[2], "days": r[3]}
        if r[0] == 2024:
            data_2024[r[1]] = entry
        else:
            data_2025[r[1]] = entry

    combined = []
    for dow in range(1, 6):
        d24 = data_2024.get(dow, {})
        d25 = data_2025.get(dow, {})
        avg_24 = d24.get('avg', 0)
        avg_25 = d25.get('avg', 0)
        pct = round((avg_25 - avg_24) / avg_24 * 100, 1) if avg_24 else None
        combined.append({
            "day": DOW_NAMES[dow],
            "avg_2024": avg_24,
            "avg_2025": avg_25,
            "change_pct": pct,
        })

    return {"city": "melbourne", "data": combined}
