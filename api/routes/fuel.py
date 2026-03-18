"""
Fuel price endpoints — retail, wholesale, and international benchmarks.
Serves Victorian fuel station prices and the oil-to-pump price chain.
"""
from fastapi import APIRouter, Query
from typing import Optional
from ..db import get_connection

router = APIRouter(prefix="/api/fuel", tags=["fuel"])


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

    # Wholesale + Brent (daily trading days)
    wholesale = con.execute(f"""
        SELECT date, mel_ulp_tgp_cpl, brent_aud_cpl, brent_usd_bbl, aud_usd_rate
        FROM wholesale_prices
        WHERE date >= CURRENT_DATE - INTERVAL '{months} months'
          AND mel_ulp_tgp_cpl IS NOT NULL
        ORDER BY date
    """).fetchall()

    # Retail daily averages (from Servo Saver snapshots)
    retail = con.execute(f"""
        SELECT snapshot_date,
               round(avg(price_cpl), 1) as avg_price,
               count(*) as stations
        FROM fuel_prices
        WHERE fuel_type = 'U91'
          AND price_cpl > 0 AND price_cpl < 500
          AND is_available = true
          AND snapshot_date >= CURRENT_DATE - INTERVAL '{months} months'
        GROUP BY snapshot_date
        ORDER BY snapshot_date
    """).fetchall()
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
        "lag_note": "ACCC methodology: Singapore Mogas 95 (7-day rolling avg) lagged 10 days approximates retail. We use Brent crude lagged 10 days as a proxy (Mogas 95 is proprietary). TGP lagged 7 days tracks retail.",
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
            SELECT date_trunc('week', CAST(ts_hour AS DATE))::DATE as week,
                   sum(vehicle_count)::bigint / count(DISTINCT CAST(ts_hour AS DATE))
                       / count(DISTINCT station_id) as avg_per_station
            FROM hourly_counts
            WHERE state = 'VIC'
              AND ISODOW(CAST(ts_hour AS DATE)) <= 5
              AND CAST(ts_hour AS DATE) >= DATE '2024-01-01'
            GROUP BY 1
            HAVING count(DISTINCT CAST(ts_hour AS DATE)) >= 3
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
