"""
Station reference endpoints — list stations with coordinates and metadata.
"""

from fastapi import APIRouter, Query
from api.db import get_connection
from api.constants import RELIABLE_NSW_IDS

router = APIRouter()


@router.get("/")
def list_stations(
    city: str = Query(..., pattern="^(sydney|melbourne)$"),
):
    """
    List all active stations for a city.
    Sydney returns only the reliable network (26 stations).
    Melbourne returns all SCATS-matched sites.
    """
    con = get_connection()
    if city == "sydney":
        ids = ",".join(f"'{s}'" for s in RELIABLE_NSW_IDS)
        where = f"station_id IN ({ids})"
    else:
        where = "state = 'VIC'"

    rows = con.execute(f"""
        SELECT station_id, road_name, suburb, road_type,
               latitude, longitude
        FROM stations
        WHERE {where}
        ORDER BY road_name
    """).fetchall()
    con.close()
    data = [{
        "station_id": r[0], "road_name": r[1], "suburb": r[2],
        "road_type": r[3], "lat": r[4], "lon": r[5],
    } for r in rows]
    return {"city": city, "count": len(data), "stations": data}
