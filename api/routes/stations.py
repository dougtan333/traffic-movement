"""
Station reference endpoints — list stations with coordinates and metadata.
Victoria only.
"""

from fastapi import APIRouter, Query
from api.db import get_connection

router = APIRouter()


@router.get("/")
def list_stations():
    """List all active VIC SCATS stations."""
    con = get_connection()
    rows = con.execute("""
        SELECT station_id, road_name, suburb, road_type,
               latitude, longitude
        FROM stations
        WHERE state = 'VIC'
        ORDER BY road_name
    """).fetchall()
    con.close()
    data = [{
        "station_id": r[0], "road_name": r[1], "suburb": r[2],
        "road_type": r[3], "lat": r[4], "lon": r[5],
    } for r in rows]
    return {"city": "melbourne", "count": len(data), "stations": data}
