"""
Fuel price endpoints — retail, wholesale, and international benchmarks.
Serves Victorian fuel station prices and the oil-to-pump price chain.
"""
from fastapi import APIRouter, Query
from typing import Optional
from datetime import date, timedelta
from ..db import get_connection

router = APIRouter(prefix="/api/fuel", tags=["fuel"])


def _months_ago(months: int) -> str:
    """Return ISO date string for approx N months before today."""
    return (date.today() - timedelta(days=months * 30)).isoformat()


@router.get("/state-average")
def state_average():
    """Daily average VIC retail fuel price by type, across all snapshots."""
    con = get_connection()
    rows = con.execute("""
        SELECT snapshot_date, fuel_type,
               round(avg(price_cpl), 1) as avg_price,
               round(min(price_cpl), 1) as min_price,
               round(max(price_cpl), 1) as max_price,
               count(*) as station_count
        FROM fuel_prices
        WHERE price_cpl > 0 AND price_cpl < 500
          AND is_available = true
        GROUP BY snapshot_date, fuel_type
        ORDER BY snapshot_date, fuel_type
    """).fetchall()
    con.close()

    return {
        "data": [
            {
                "date": str(r[0]), "fuel_type": r[1],
                "avg_price": r[2], "min_price": r[3], "max_price": r[4],
                "stations": r[5],
            }
            for r in rows
        ],
    }


@router.get("/by-postcode")
def by_postcode(
    postcode: str = Query(..., description="4-digit VIC postcode"),
    fuel_type: str = Query("U91"),
):
    """Cheapest and most expensive stations in a postcode, latest snapshot."""
    con = get_connection()
    rows = con.execute("""
        SELECT fs.name, fs.brand_name, fs.address, fs.latitude, fs.longitude,
               fp.price_cpl, fp.snapshot_date, fp.fuel_type
        FROM fuel_prices fp
        JOIN fuel_stations fs ON fp.station_id = fs.station_id
        WHERE fs.postcode = ?
          AND fp.fuel_type = ?
          AND fp.price_cpl > 0 AND fp.price_cpl < 500
          AND fp.is_available = true
          AND fp.snapshot_date = (SELECT max(snapshot_date) FROM fuel_prices)
        ORDER BY fp.price_cpl ASC
    """, [postcode, fuel_type]).fetchall()
    con.close()

    return {
        "postcode": postcode,
        "fuel_type": fuel_type,
        "date": str(rows[0][6]) if rows else None,
        "stations": [
            {
                "name": r[0], "brand": r[1], "address": r[2],
                "lat": r[3], "lon": r[4], "price_cpl": r[5],
            }
            for r in rows
        ],
    }


@router.get("/postcodes")
def postcodes():
    """List all postcodes with station counts, for the dropdown selector."""
    con = get_connection()
    rows = con.execute("""
        SELECT postcode, count(*) as stations,
               min(suburb) as example_suburb
        FROM fuel_stations
        WHERE postcode IS NOT NULL
        GROUP BY postcode
        ORDER BY postcode
    """).fetchall()
    con.close()

    return {
        "postcodes": [
            {"postcode": r[0], "stations": r[1], "suburb": r[2]}
            for r in rows
        ],
    }


@router.get("/heatmap")
def heatmap(fuel_type: str = Query("U91")):
    """All station prices with coordinates for map display, latest snapshot."""
    con = get_connection()
    rows = con.execute("""
        SELECT fs.station_id, fs.name, fs.brand_name, fs.suburb, fs.postcode,
               fs.latitude, fs.longitude,
               fp.price_cpl, fp.snapshot_date
        FROM fuel_prices fp
        JOIN fuel_stations fs ON fp.station_id = fs.station_id
        WHERE fp.fuel_type = ?
          AND fp.price_cpl > 0 AND fp.price_cpl < 500
          AND fp.is_available = true
          AND fs.latitude IS NOT NULL
          AND fp.snapshot_date = (SELECT max(snapshot_date) FROM fuel_prices)
        ORDER BY fp.price_cpl ASC
    """, [fuel_type]).fetchall()
    con.close()

    return {
        "fuel_type": fuel_type,
        "date": str(rows[0][8]) if rows else None,
        "stations": [
            {
                "id": r[0], "name": r[1], "brand": r[2],
                "suburb": r[3], "postcode": r[4],
                "lat": r[5], "lon": r[6], "price_cpl": r[7],
            }
            for r in rows
        ],
    }


@router.get("/price-chain")
def price_chain(months: int = Query(6, description="Months of history")):
    """Oil-to-pump price chain: Brent crude, Melbourne TGP, VIC retail avg.
    
    Returns three series for overlay charting:
    - Brent crude (AUD cents/litre) — the international benchmark
    - Melbourne ULP TGP — the wholesale price
    - VIC retail average ULP — what you pay at the pump
    
    Brent and TGP include lag-shifted versions for comparison:
    - Brent lagged 10 days forward (ACCC standard)
    - TGP lagged 7 days forward
    """
    con = get_connection()

    # Wholesale + Brent (daily trading days) — include rows with either TGP or Brent
    cutoff = _months_ago(months)
    wholesale = con.execute("""
        SELECT date, mel_ulp_tgp_cpl, brent_aud_cpl, brent_usd_bbl, aud_usd_rate
        FROM wholesale_prices
        WHERE date >= ?::DATE
          AND (mel_ulp_tgp_cpl IS NOT NULL OR brent_usd_bbl IS NOT NULL)
        ORDER BY date
    """, [cutoff]).fetchall()

    # Latest Brent price (may be more recent than TGP)
    latest_brent = con.execute("""
        SELECT date, brent_usd_bbl, aud_usd_rate, brent_aud_cpl
        FROM wholesale_prices
        WHERE brent_usd_bbl IS NOT NULL
        ORDER BY date DESC LIMIT 1
    """).fetchone()

    # Retail daily averages (from Servo Saver snapshots)
    retail = con.execute("""
        SELECT snapshot_date,
               round(avg(price_cpl), 1) as avg_price,
               count(*) as stations
        FROM fuel_prices
        WHERE fuel_type = 'U91'
          AND price_cpl > 0 AND price_cpl < 500
          AND is_available = true
          AND snapshot_date >= ?::DATE
        GROUP BY snapshot_date
        ORDER BY snapshot_date
    """, [cutoff]).fetchall()
    con.close()

    return {
        "wholesale": [
            {
                "date": str(r[0]),
                "mel_tgp_cpl": r[1],
                "brent_aud_cpl": r[2],
                "brent_usd_bbl": float(r[3]) if r[3] else None,
                "aud_usd": float(r[4]) if r[4] else None,
            }
            for r in wholesale
        ],
        "retail": [
            {"date": str(r[0]), "avg_u91_cpl": r[1], "stations": r[2]}
            for r in retail
        ],
        "latest_brent": {
            "date": str(latest_brent[0]) if latest_brent else None,
            "usd_bbl": float(latest_brent[1]) if latest_brent else None,
            "aud_usd": float(latest_brent[2]) if latest_brent and latest_brent[2] else None,
            "aud_cpl": float(latest_brent[3]) if latest_brent and latest_brent[3] else None,
        } if latest_brent else None,
        "lag_note": "ACCC methodology: Singapore Mogas 95 (7-day rolling avg) lagged 10 days approximates retail. We use Brent crude as a proxy (Mogas 95 is proprietary). TGP lagged 7 days tracks retail.",
    }


@router.get("/traffic-overlay")
def traffic_overlay():
    """Weekly traffic volume alongside weekly average fuel price.
    
    For the key question: does traffic drop when fuel prices spike?
    Uses Melbourne SCATS weekday avg per station vs Melbourne TGP.
    """
    con = get_connection()
    rows = con.execute("""
        WITH weekly_traffic AS (
            SELECT date_trunc('week', day)::DATE as week,
                   sum(daily_total)::bigint / count(DISTINCT day)
                       / count(DISTINCT station_id) as avg_per_station
            FROM daily_station_summary
            WHERE is_weekday = true
              AND day >= DATE '2024-01-01'
            GROUP BY 1
            HAVING count(DISTINCT day) >= 3
        ),
        weekly_price AS (
            SELECT date_trunc('week', date)::DATE as week,
                   round(avg(mel_ulp_tgp_cpl), 1) as avg_tgp
            FROM wholesale_prices
            WHERE mel_ulp_tgp_cpl IS NOT NULL
              AND date >= DATE '2024-01-01'
            GROUP BY 1
        )
        SELECT t.week, t.avg_per_station, p.avg_tgp
        FROM weekly_traffic t
        LEFT JOIN weekly_price p ON t.week = p.week
        ORDER BY t.week
    """).fetchall()
    con.close()

    return {
        "data": [
            {
                "week": str(r[0]),
                "traffic_avg_per_station": int(r[1]),
                "tgp_cpl": float(r[2]) if r[2] else None,
            }
            for r in rows
        ],
    }


@router.get("/nearby")
def nearby_fuel(lat: float = Query(...), lon: float = Query(...), limit: int = Query(3)):
    """
    Find the nearest fuel stations to a given lat/lon and return
    their latest U91 price. Uses simple Euclidean distance on lat/lon
    (good enough at city scale for ranking).
    """
    con = get_connection()
    rows = con.execute("""
        WITH latest AS (
            SELECT MAX(snapshot_date) as d FROM fuel_prices
        ),
        nearby AS (
            SELECT
                s.station_id,
                s.name,
                s.brand_name,
                s.address,
                s.suburb,
                s.latitude,
                s.longitude,
                -- Approx distance in km (crude Euclidean, fine for ranking within a city)
                SQRT(POW((s.latitude - ?) * 111.32, 2) + POW((s.longitude - ?) * 111.32 * COS(RADIANS(?)), 2)) as dist_km
            FROM fuel_stations s
            WHERE s.latitude IS NOT NULL
            ORDER BY dist_km
            LIMIT ?
        )
        SELECT
            n.station_id, n.name, n.brand_name, n.address, n.suburb,
            n.latitude, n.longitude, ROUND(n.dist_km, 1) as dist_km,
            p.fuel_type, p.price_cpl
        FROM nearby n
        LEFT JOIN fuel_prices p
            ON n.station_id = p.station_id
            AND p.snapshot_date = (SELECT d FROM latest)
            AND p.price_cpl > 0 AND p.price_cpl < 500
            AND p.is_available = true
        ORDER BY n.dist_km, p.fuel_type
    """, [lat, lon, lat, limit]).fetchall()
    con.close()

    # Group by station
    stations = {}
    for r in rows:
        sid = r[0]
        if sid not in stations:
            stations[sid] = {
                "station_id": sid, "name": r[1], "brand": r[2],
                "address": r[3], "suburb": r[4],
                "lat": r[5], "lon": r[6], "dist_km": float(r[7]),
                "prices": {},
            }
        if r[8]:
            stations[sid]["prices"][r[8]] = float(r[9])

    return {"stations": list(stations.values())}



@router.get("/outages")
def outages(state: str = Query("VIC")):
    """Daily fuel outage counts by fuel type, excluding structural non-sellers.

    A station is 'structurally unavailable' for a fuel type if it has NEVER
    reported that type as available in our data. These are filtered out so
    the metric reflects genuine supply disruption, not stations that simply
    don't stock a given fuel.

    Returns one row per (date, fuel_type) with total stations, unavailable
    count, and percentage. Uses the latest snapshot_period per day (PM if
    available, else AM).
    """
    con = get_connection()
    rows = con.execute("""
        WITH latest_period AS (
            -- Pick the latest snapshot_period per day (PM > AM)
            SELECT snapshot_date,
                   max(snapshot_period) as period
            FROM fuel_prices
            GROUP BY snapshot_date
        ),
        structural_unavail AS (
            -- Stations that have NEVER been available for a fuel type
            SELECT station_id, fuel_type
            FROM fuel_prices
            GROUP BY station_id, fuel_type
            HAVING max(case when is_available then 1 else 0 end) = 0
        ),
        filtered AS (
            SELECT fp.snapshot_date, fp.fuel_type,
                   fp.is_available
            FROM fuel_prices fp
            JOIN latest_period lp
                ON fp.snapshot_date = lp.snapshot_date
                AND fp.snapshot_period = lp.period
            WHERE NOT EXISTS (
                SELECT 1 FROM structural_unavail su
                WHERE su.station_id = fp.station_id
                  AND su.fuel_type = fp.fuel_type
            )
        )
        SELECT snapshot_date, fuel_type,
               count(*) as total_stations,
               sum(case when not is_available then 1 else 0 end) as unavailable,
               round(100.0 * sum(case when not is_available then 1 else 0 end)
                     / count(*), 1) as pct_out
        FROM filtered
        GROUP BY snapshot_date, fuel_type
        ORDER BY snapshot_date, fuel_type
    """).fetchall()
    con.close()

    return {
        "state": state,
        "data": [
            {
                "date": str(r[0]),
                "fuel_type": r[1],
                "total_stations": r[2],
                "unavailable": r[3],
                "pct_out": float(r[4]),
            }
            for r in rows
        ],
    }


@router.get("/outage-map")
def outage_map(fuel_type: str = Query("DSL")):
    """Station-level availability for map display, latest snapshot.

    Returns all stations with their availability status for the given
    fuel type. Frontend colours: green = available, red = unavailable.
    Excludes stations that have never stocked the fuel type.
    """
    con = get_connection()
    rows = con.execute("""
        WITH latest AS (
            SELECT max(snapshot_date) as d,
                   max(snapshot_period) as p
            FROM fuel_prices
            WHERE snapshot_date = (SELECT max(snapshot_date) FROM fuel_prices)
        ),
        structural_unavail AS (
            SELECT station_id, fuel_type
            FROM fuel_prices
            GROUP BY station_id, fuel_type
            HAVING max(case when is_available then 1 else 0 end) = 0
        )
        SELECT fs.station_id, fs.name, fs.brand_name, fs.suburb,
               fs.postcode, fs.latitude, fs.longitude,
               fp.is_available, fp.price_cpl, fp.snapshot_date
        FROM fuel_prices fp
        JOIN fuel_stations fs ON fp.station_id = fs.station_id
        CROSS JOIN latest l
        WHERE fp.fuel_type = ?
          AND fp.snapshot_date = l.d
          AND fp.snapshot_period = l.p
          AND fs.latitude IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM structural_unavail su
              WHERE su.station_id = fp.station_id
                AND su.fuel_type = fp.fuel_type
          )
        ORDER BY fp.is_available, fs.suburb
    """, [fuel_type]).fetchall()
    con.close()

    return {
        "fuel_type": fuel_type,
        "date": str(rows[0][9]) if rows else None,
        "total": len(rows),
        "unavailable": sum(1 for r in rows if not r[7]),
        "stations": [
            {
                "id": r[0], "name": r[1], "brand": r[2],
                "suburb": r[3], "postcode": r[4],
                "lat": r[5], "lon": r[6],
                "available": r[7],
                "price_cpl": float(r[8]) if r[8] else None,
            }
            for r in rows
        ],
    }


@router.get("/outage-summary")
def outage_summary(state: str = Query("VIC")):
    """Headline outage stats for dashboard metric cards.

    Returns latest-day stats for major fuel types (U91, P95, P98, DSL, E10, LPG):
    total stations, unavailable count, % out, and average price.
    """
    con = get_connection()
    rows = con.execute("""
        WITH latest AS (
            SELECT max(snapshot_date) as d,
                   max(snapshot_period) as p
            FROM fuel_prices
            WHERE snapshot_date = (SELECT max(snapshot_date) FROM fuel_prices)
        ),
        structural_unavail AS (
            SELECT station_id, fuel_type
            FROM fuel_prices
            GROUP BY station_id, fuel_type
            HAVING max(case when is_available then 1 else 0 end) = 0
        )
        SELECT fp.fuel_type,
               count(*) as total,
               sum(case when not fp.is_available then 1 else 0 end) as unavailable,
               round(100.0 * sum(case when not fp.is_available then 1 else 0 end)
                     / count(*), 1) as pct_out,
               round(avg(case when fp.is_available and fp.price_cpl > 0
                         then fp.price_cpl end), 1) as avg_price,
               l.d as snapshot_date
        FROM fuel_prices fp
        CROSS JOIN latest l
        WHERE fp.snapshot_date = l.d
          AND fp.snapshot_period = l.p
          AND fp.fuel_type IN ('U91', 'P95', 'P98', 'DSL', 'E10', 'LPG')
          AND NOT EXISTS (
              SELECT 1 FROM structural_unavail su
              WHERE su.station_id = fp.station_id
                AND su.fuel_type = fp.fuel_type
          )
        GROUP BY fp.fuel_type, l.d
        ORDER BY total DESC
    """).fetchall()
    con.close()

    return {
        "state": state,
        "date": str(rows[0][5]) if rows else None,
        "fuel_types": [
            {
                "fuel_type": r[0],
                "total_stations": r[1],
                "unavailable": r[2],
                "pct_out": float(r[3]),
                "avg_price_cpl": float(r[4]) if r[4] else None,
            }
            for r in rows
        ],
    }
