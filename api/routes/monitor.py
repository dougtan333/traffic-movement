"""
Weekly monitor endpoint — fuel crisis tracker.

Returns the latest weekly comparison report: current week vs
Feb 2026 baseline, vs prior week, vs same week last year.
Victoria only.
"""

from fastapi import APIRouter
from api.db import get_connection
from datetime import date

router = APIRouter()

BASELINE_START = "2026-02-01"
BASELINE_END = "2026-02-28"
CRISIS_DATE = "2026-03-03"
VIC_FILTER = "h.state = 'VIC'"


@router.get("/")
def monitor_report():
    """Weekly fuel crisis monitor — Victoria."""
    con = get_connection()

    freshness = con.execute("""
        SELECT max(ts_hour)::DATE as latest FROM hourly_counts WHERE state = 'VIC'
    """).fetchone()

    # Weekly trend (last 12 weeks)
    weeks = con.execute(f"""
        SELECT date_trunc('week', CAST(ts_hour AS DATE))::DATE as week,
               sum(vehicle_count)::bigint
                   / count(DISTINCT CAST(ts_hour AS DATE))
                   / count(DISTINCT station_id) as avg_per_station,
               count(DISTINCT CAST(ts_hour AS DATE)) as days,
               count(DISTINCT station_id) as stations
        FROM hourly_counts h
        WHERE {VIC_FILTER} AND ISODOW(CAST(ts_hour AS DATE)) <= 5
          AND ts_hour >= '2026-01-01'
        GROUP BY 1
        HAVING count(DISTINCT CAST(ts_hour AS DATE)) >= 3
        ORDER BY 1
    """).fetchall()

    # Baseline
    baseline = con.execute(f"""
        SELECT sum(vehicle_count)::bigint
               / count(DISTINCT CAST(ts_hour AS DATE))
               / count(DISTINCT station_id)
        FROM hourly_counts h
        WHERE {VIC_FILTER} AND ISODOW(CAST(ts_hour AS DATE)) <= 5
          AND CAST(ts_hour AS DATE) BETWEEN '{BASELINE_START}' AND '{BASELINE_END}'
    """).fetchone()[0]
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
    }
