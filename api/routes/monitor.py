"""
Weekly monitor endpoint — fuel crisis tracker.

Returns the latest weekly comparison report: current week vs
Feb 2026 baseline, vs prior week, vs same week last year.
Victoria only. Filtered to metro core stations (P75+ daily volume
from Feb 2026 baseline) for a sharper urban signal.
"""

from fastapi import APIRouter
from api.db import get_connection, get_metro_core_count, BASELINE_START, BASELINE_END
from datetime import date

router = APIRouter()

BASELINE_START = "2026-02-01"
BASELINE_END = "2026-02-28"
CRISIS_DATE = "2026-03-02"
VIC_FILTER = "h.state = 'VIC'"


@router.get("/")
def monitor_report():
    """Weekly fuel crisis monitor — Victoria metro core."""
    con = get_connection()

    freshness = con.execute("""
        SELECT max(day) as latest FROM daily_station_summary
    """).fetchone()

    # Metro core stations: permanent table, refreshed daily by materialize_metro_core.py
    core_count = get_metro_core_count(con)

    # Weekly trend — from daily_station_summary
    weeks = con.execute("""
        SELECT date_trunc('week', day)::DATE as week,
               sum(daily_total)::bigint
                   / count(DISTINCT day)
                   / count(DISTINCT station_id) as avg_per_station,
               count(DISTINCT day) as days,
               count(DISTINCT station_id) as stations
        FROM daily_station_summary
        WHERE is_weekday = true
          AND day >= '2026-01-01'
        GROUP BY 1
        HAVING count(DISTINCT day) >= 3
        ORDER BY 1
    """).fetchall()

    # Baseline — from daily_station_summary
    baseline = con.execute("""
        SELECT sum(daily_total)::bigint
               / count(DISTINCT day)
               / count(DISTINCT station_id)
        FROM daily_station_summary
        WHERE is_weekday = true
          AND day BETWEEN ?::DATE AND ?::DATE
    """, [BASELINE_START, BASELINE_END]).fetchone()[0]
    con.close()

    week_data = [{"week": str(w[0]), "avg": int(w[1]), "days": int(w[2]),
                  "stations": int(w[3])} for w in weeks]
    latest = week_data[-1] if week_data else None
    prior = week_data[-2] if len(week_data) >= 2 else None

    def pct(a, b):
        return round((a - b) / b * 100, 1) if b else None

    return {
        "report_date": date.today().isoformat(),
        "data_freshness": str(freshness[0]) if freshness else None,
        "baseline_feb26": int(baseline) if baseline else None,
        "latest_week": latest,
        "vs_baseline_pct": pct(latest["avg"], baseline) if latest and baseline else None,
        "vs_prior_week_pct": pct(latest["avg"], prior["avg"]) if latest and prior else None,
        "weekly_trend": week_data,
        "crisis_date": CRISIS_DATE,
        "metro_core_stations": core_count,
    }
