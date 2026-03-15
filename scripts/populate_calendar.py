"""
AMIP Calendar Population — NSW & VIC (2020–2026)

Populates the calendar table with:
  - Day-of-week, week number, month, year, season (Southern Hemisphere)
  - NSW & VIC public holidays (national + state-specific)
  - NSW & VIC school holiday periods (approximate term boundaries)
  - Major events: AFL GF, Melbourne Cup, NRL GF, Australian Open, NYE

Sources: Official state government gazettes and education department
term dates. Where 2026 dates are not yet gazetted, projected from
prior-year patterns (flagged in comments).

Prerequisite: Run create_schema.py first to create the calendar table.

Usage:
  python scripts/populate_calendar.py        # from project root
  python populate_calendar.py                # from scripts/
"""

from pathlib import Path
from datetime import date, timedelta
import duckdb

# Resolve db path relative to project root (one level up from scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "amip.duckdb"


# ── Southern Hemisphere seasons ───────────────────────────────────────
def get_season(d: date) -> str:
    month = d.month
    if month in (12, 1, 2):
        return "summer"
    elif month in (3, 4, 5):
        return "autumn"
    elif month in (6, 7, 8):
        return "winter"
    else:
        return "spring"


# ── Public Holidays ───────────────────────────────────────────────────
# National holidays observed in both states, plus state-specific ones.
# Easter dates shift yearly — all included below.

NSW_HOLIDAYS: dict[date, str] = {}
VIC_HOLIDAYS: dict[date, str] = {}

def _add_national(d: date, name: str):
    """Add to both states."""
    NSW_HOLIDAYS[d] = name
    VIC_HOLIDAYS[d] = name

def _add_nsw(d: date, name: str):
    NSW_HOLIDAYS[d] = name

def _add_vic(d: date, name: str):
    VIC_HOLIDAYS[d] = name


# --- 2020 ---
_add_national(date(2020,  1,  1), "New Year's Day")
_add_national(date(2020,  1, 27), "Australia Day (observed)")
_add_national(date(2020,  4, 10), "Good Friday")
_add_national(date(2020,  4, 11), "Saturday before Easter Sunday")
_add_national(date(2020,  4, 13), "Easter Monday")
_add_national(date(2020,  4, 25), "ANZAC Day")
_add_national(date(2020,  6,  8), "Queen's Birthday (NSW/VIC)")
_add_national(date(2020, 12, 25), "Christmas Day")
_add_national(date(2020, 12, 26), "Boxing Day")
_add_national(date(2020, 12, 28), "Boxing Day (observed)")
_add_nsw(date(2020,  8,  3), "Bank Holiday NSW")
_add_vic(date(2020, 11,  3), "Melbourne Cup Day")

# --- 2021 ---
_add_national(date(2021,  1,  1), "New Year's Day")
_add_national(date(2021,  1, 26), "Australia Day")
_add_national(date(2021,  4,  2), "Good Friday")
_add_national(date(2021,  4,  3), "Saturday before Easter Sunday")
_add_national(date(2021,  4,  5), "Easter Monday")
_add_national(date(2021,  4, 25), "ANZAC Day")
_add_national(date(2021,  6, 14), "Queen's Birthday (NSW/VIC)")
_add_national(date(2021, 12, 25), "Christmas Day")
_add_national(date(2021, 12, 27), "Christmas Day (observed)")
_add_national(date(2021, 12, 28), "Boxing Day (observed)")
_add_nsw(date(2021,  8,  2), "Bank Holiday NSW")
_add_vic(date(2021, 11,  2), "Melbourne Cup Day")
_add_vic(date(2021,  9, 24), "AFL Grand Final Friday")

# --- 2022 ---
_add_national(date(2022,  1,  1), "New Year's Day")
_add_national(date(2022,  1,  3), "New Year's Day (observed)")
_add_national(date(2022,  1, 26), "Australia Day")
_add_national(date(2022,  4, 15), "Good Friday")
_add_national(date(2022,  4, 16), "Saturday before Easter Sunday")
_add_national(date(2022,  4, 18), "Easter Monday")
_add_national(date(2022,  4, 25), "ANZAC Day")
_add_national(date(2022,  6, 13), "Queen's Birthday (NSW/VIC)")
_add_national(date(2022,  9, 22), "National Day of Mourning")
_add_national(date(2022, 12, 25), "Christmas Day")
_add_national(date(2022, 12, 26), "Boxing Day")
_add_national(date(2022, 12, 27), "Christmas Day (observed)")
_add_nsw(date(2022,  8,  1), "Bank Holiday NSW")
_add_vic(date(2022, 11,  1), "Melbourne Cup Day")
_add_vic(date(2022,  9, 23), "AFL Grand Final Friday")

# --- 2023 ---
_add_national(date(2023,  1,  1), "New Year's Day")
_add_national(date(2023,  1,  2), "New Year's Day (observed)")
_add_national(date(2023,  1, 26), "Australia Day")
_add_national(date(2023,  4,  7), "Good Friday")
_add_national(date(2023,  4,  8), "Saturday before Easter Sunday")
_add_national(date(2023,  4, 10), "Easter Monday")
_add_national(date(2023,  4, 25), "ANZAC Day")
_add_national(date(2023,  6, 12), "King's Birthday (NSW/VIC)")
_add_national(date(2023, 12, 25), "Christmas Day")
_add_national(date(2023, 12, 26), "Boxing Day")
_add_nsw(date(2023,  8,  7), "Bank Holiday NSW")
_add_vic(date(2023, 11,  7), "Melbourne Cup Day")
_add_vic(date(2023,  9, 29), "AFL Grand Final Friday")

# --- 2024 ---
_add_national(date(2024,  1,  1), "New Year's Day")
_add_national(date(2024,  1, 26), "Australia Day")
_add_national(date(2024,  3, 29), "Good Friday")
_add_national(date(2024,  3, 30), "Saturday before Easter Sunday")
_add_national(date(2024,  4,  1), "Easter Monday")
_add_national(date(2024,  4, 25), "ANZAC Day")
_add_national(date(2024,  6, 10), "King's Birthday (NSW/VIC)")
_add_national(date(2024, 12, 25), "Christmas Day")
_add_national(date(2024, 12, 26), "Boxing Day")
_add_nsw(date(2024,  8,  5), "Bank Holiday NSW")
_add_vic(date(2024, 11,  5), "Melbourne Cup Day")
_add_vic(date(2024,  9, 27), "AFL Grand Final Friday")

# --- 2025 ---
_add_national(date(2025,  1,  1), "New Year's Day")
_add_national(date(2025,  1, 27), "Australia Day (observed)")
_add_national(date(2025,  4, 18), "Good Friday")
_add_national(date(2025,  4, 19), "Saturday before Easter Sunday")
_add_national(date(2025,  4, 21), "Easter Monday")
_add_national(date(2025,  4, 25), "ANZAC Day")
_add_national(date(2025,  6,  9), "King's Birthday (NSW/VIC)")
_add_national(date(2025, 12, 25), "Christmas Day")
_add_national(date(2025, 12, 26), "Boxing Day")
_add_nsw(date(2025,  8,  4), "Bank Holiday NSW")
_add_vic(date(2025, 11,  4), "Melbourne Cup Day")
_add_vic(date(2025,  9, 26), "AFL Grand Final Friday")

# --- 2026 ---
_add_national(date(2026,  1,  1), "New Year's Day")
_add_national(date(2026,  1, 26), "Australia Day")
_add_national(date(2026,  4,  3), "Good Friday")
_add_national(date(2026,  4,  4), "Saturday before Easter Sunday")
_add_national(date(2026,  4,  6), "Easter Monday")
_add_national(date(2026,  4, 25), "ANZAC Day")
_add_national(date(2026,  6,  8), "King's Birthday (NSW/VIC)")
_add_national(date(2026, 12, 25), "Christmas Day")
_add_national(date(2026, 12, 26), "Boxing Day")
_add_national(date(2026, 12, 28), "Boxing Day (observed)")
_add_nsw(date(2026,  8,  3), "Bank Holiday NSW")
_add_vic(date(2026, 11,  3), "Melbourne Cup Day (projected)")
_add_vic(date(2026,  9, 25), "AFL Grand Final Friday (projected)")


# ── School Holidays ───────────────────────────────────────────────────
# Stored as (start, end) inclusive date ranges per state per year.
# Sources: NSW DoE and VIC DET published term dates.
# 2026 dates are projected from typical patterns where not yet gazetted.

NSW_SCHOOL_HOLIDAYS: list[tuple[date, date]] = [
    # 2020
    (date(2020,  1,  1), date(2020,  1, 27)),  # Summer
    (date(2020,  4, 13), date(2020,  4, 24)),  # Autumn
    (date(2020,  7,  6), date(2020,  7, 17)),  # Winter
    (date(2020,  9, 28), date(2020, 10,  9)),  # Spring
    (date(2020, 12, 19), date(2020, 12, 31)),  # Summer start
    # 2021
    (date(2021,  1,  1), date(2021,  1, 26)),
    (date(2021,  4, 12), date(2021,  4, 23)),
    (date(2021,  7,  5), date(2021,  7, 16)),
    (date(2021,  9, 27), date(2021, 10,  8)),
    (date(2021, 12, 20), date(2021, 12, 31)),
    # 2022
    (date(2022,  1,  1), date(2022,  1, 28)),
    (date(2022,  4, 11), date(2022,  4, 22)),
    (date(2022,  7,  4), date(2022,  7, 15)),
    (date(2022,  9, 26), date(2022, 10,  7)),
    (date(2022, 12, 20), date(2022, 12, 31)),
    # 2023
    (date(2023,  1,  1), date(2023,  1, 27)),
    (date(2023,  4, 14), date(2023,  4, 24)),
    (date(2023,  7,  7), date(2023,  7, 17)),
    (date(2023,  9, 25), date(2023, 10,  6)),
    (date(2023, 12, 20), date(2023, 12, 31)),
    # 2024
    (date(2024,  1,  1), date(2024,  1, 26)),
    (date(2024,  4, 15), date(2024,  4, 26)),
    (date(2024,  7,  8), date(2024,  7, 19)),
    (date(2024,  9, 30), date(2024, 10, 11)),
    (date(2024, 12, 20), date(2024, 12, 31)),
    # 2025
    (date(2025,  1,  1), date(2025,  1, 28)),
    (date(2025,  4, 14), date(2025,  4, 25)),
    (date(2025,  7,  7), date(2025,  7, 18)),
    (date(2025,  9, 29), date(2025, 10, 10)),
    (date(2025, 12, 19), date(2025, 12, 31)),
    # 2026 (projected)
    (date(2026,  1,  1), date(2026,  1, 27)),
    (date(2026,  4, 13), date(2026,  4, 24)),
    (date(2026,  7,  6), date(2026,  7, 17)),
    (date(2026,  9, 28), date(2026, 10,  9)),
    (date(2026, 12, 18), date(2026, 12, 31)),
]

VIC_SCHOOL_HOLIDAYS: list[tuple[date, date]] = [
    # 2020
    (date(2020,  1,  1), date(2020,  1, 28)),
    (date(2020,  3, 28), date(2020,  4, 13)),
    (date(2020,  6, 27), date(2020,  7, 12)),
    (date(2020,  9, 19), date(2020, 10,  4)),
    (date(2020, 12, 19), date(2020, 12, 31)),
    # 2021
    (date(2021,  1,  1), date(2021,  1, 27)),
    (date(2021,  4,  2), date(2021,  4, 18)),
    (date(2021,  6, 26), date(2021,  7, 11)),
    (date(2021,  9, 18), date(2021, 10,  3)),
    (date(2021, 12, 18), date(2021, 12, 31)),
    # 2022
    (date(2022,  1,  1), date(2022,  1, 28)),
    (date(2022,  4,  9), date(2022,  4, 25)),
    (date(2022,  6, 25), date(2022,  7, 10)),
    (date(2022,  9, 17), date(2022, 10,  2)),
    (date(2022, 12, 21), date(2022, 12, 31)),
    # 2023
    (date(2023,  1,  1), date(2023,  1, 27)),
    (date(2023,  4,  7), date(2023,  4, 23)),
    (date(2023,  6, 24), date(2023,  7,  9)),
    (date(2023,  9, 16), date(2023, 10,  1)),
    (date(2023, 12, 21), date(2023, 12, 31)),
    # 2024
    (date(2024,  1,  1), date(2024,  1, 29)),
    (date(2024,  3, 29), date(2024,  4, 14)),
    (date(2024,  6, 29), date(2024,  7, 14)),
    (date(2024,  9, 21), date(2024, 10,  6)),
    (date(2024, 12, 21), date(2024, 12, 31)),
    # 2025
    (date(2025,  1,  1), date(2025,  1, 28)),
    (date(2025,  4,  5), date(2025,  4, 21)),
    (date(2025,  7,  5), date(2025,  7, 20)),
    (date(2025,  9, 20), date(2025, 10,  5)),
    (date(2025, 12, 20), date(2025, 12, 31)),
    # 2026 (projected)
    (date(2026,  1,  1), date(2026,  1, 28)),
    (date(2026,  4,  4), date(2026,  4, 19)),
    (date(2026,  6, 27), date(2026,  7, 12)),
    (date(2026,  9, 19), date(2026, 10,  4)),
    (date(2026, 12, 19), date(2026, 12, 31)),
]


# ── Major Events (multi-state) ────────────────────────────────────────
# Keyed by date. For multi-day events, only the primary date is tagged
# (e.g. AFL GF day, Melbourne Cup day, NYE).

EVENTS: dict[date, str] = {
    # NYE
    date(2020, 12, 31): "New Year's Eve",
    date(2021, 12, 31): "New Year's Eve",
    date(2022, 12, 31): "New Year's Eve",
    date(2023, 12, 31): "New Year's Eve",
    date(2024, 12, 31): "New Year's Eve",
    date(2025, 12, 31): "New Year's Eve",
    # AFL Grand Final
    date(2020, 10, 24): "AFL Grand Final",
    date(2021,  9, 25): "AFL Grand Final",
    date(2022,  9, 24): "AFL Grand Final",
    date(2023,  9, 30): "AFL Grand Final",
    date(2024,  9, 28): "AFL Grand Final",
    date(2025,  9, 27): "AFL Grand Final",
    date(2026,  9, 26): "AFL Grand Final (projected)",
    # Melbourne Cup
    date(2020, 11,  3): "Melbourne Cup",
    date(2021, 11,  2): "Melbourne Cup",
    date(2022, 11,  1): "Melbourne Cup",
    date(2023, 11,  7): "Melbourne Cup",
    date(2024, 11,  5): "Melbourne Cup",
    date(2025, 11,  4): "Melbourne Cup",
    date(2026, 11,  3): "Melbourne Cup (projected)",
    # NRL Grand Final
    date(2020, 10, 25): "NRL Grand Final",
    date(2021, 10,  3): "NRL Grand Final",
    date(2022, 10,  2): "NRL Grand Final",
    date(2023, 10,  1): "NRL Grand Final",
    date(2024, 10,  6): "NRL Grand Final",
    date(2025, 10,  5): "NRL Grand Final (projected)",
    date(2026, 10,  4): "NRL Grand Final (projected)",
    # Australian Open (men's final Sunday)
    date(2020,  2,  2): "Australian Open Final",
    date(2021,  2, 21): "Australian Open Final",
    date(2022,  1, 30): "Australian Open Final",
    date(2023,  1, 29): "Australian Open Final",
    date(2024,  1, 28): "Australian Open Final",
    date(2025,  1, 26): "Australian Open Final",
    date(2026,  2,  1): "Australian Open Final (projected)",
}


def _in_range(d: date, ranges: list[tuple[date, date]]) -> bool:
    return any(start <= d <= end for start, end in ranges)


def populate_calendar(con: duckdb.DuckDBPyConnection) -> int:
    """Insert rows for 2020-01-01 to 2026-12-31. Returns row count."""
    start = date(2020, 1, 1)
    end = date(2026, 12, 31)
    rows = []
    d = start
    while d <= end:
        iso_dow = d.isoweekday()  # 1=Mon .. 7=Sun
        rows.append((
            d,
            iso_dow,
            iso_dow <= 5,
            d.isocalendar()[1],
            d.month,
            d.year,
            d in NSW_HOLIDAYS,
            d in VIC_HOLIDAYS,
            _in_range(d, NSW_SCHOOL_HOLIDAYS),
            _in_range(d, VIC_SCHOOL_HOLIDAYS),
            EVENTS.get(d),
            get_season(d),
        ))
        d += timedelta(days=1)

    con.execute("DELETE FROM calendar;")  # idempotent re-run
    con.executemany("""
        INSERT INTO calendar VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

    count = con.execute("SELECT COUNT(*) FROM calendar").fetchone()[0]
    return count


if __name__ == "__main__":
    con = duckdb.connect(str(DB_PATH))
    count = populate_calendar(con)
    print(f"Calendar populated: {count} rows ({date(2020,1,1)} → {date(2026,12,31)})")

    # Quick stats
    stats = con.execute("""
        SELECT
            COUNT(*) FILTER (WHERE is_public_holiday_nsw) as nsw_holidays,
            COUNT(*) FILTER (WHERE is_public_holiday_vic) as vic_holidays,
            COUNT(*) FILTER (WHERE is_school_holiday_nsw) as nsw_school_days,
            COUNT(*) FILTER (WHERE is_school_holiday_vic) as vic_school_days,
            COUNT(*) FILTER (WHERE event_name IS NOT NULL) as event_days
        FROM calendar;
    """).fetchone()

    print(f"  NSW public holidays:  {stats[0]}")
    print(f"  VIC public holidays:  {stats[1]}")
    print(f"  NSW school hol days:  {stats[2]}")
    print(f"  VIC school hol days:  {stats[3]}")
    print(f"  Major event dates:    {stats[4]}")
    con.close()
