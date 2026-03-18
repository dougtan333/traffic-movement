"""
AMIP DuckDB Schema — V1
Creates the core tables for the Australia Mobility Intelligence Platform.

Tables:
  - stations:            Unified station/site reference (NSW + VIC)
  - hourly_counts:       Hourly vehicle counts per station (core fact table)
  - bluetooth_routes:    VIC Bluetooth route reference (geometry + metadata)
  - speed_observations:  Speed & travel time per route interval (VIC only for V1)
  - calendar:            Date dimension with holidays, school terms, events
  - data_modules:        Manifest of active data sources (per PROJECT_REFERENCE)
  - fuel_stations:       VIC fuel station reference (Servo Saver API)
  - fuel_prices:         Daily retail fuel price snapshots per station (Servo Saver API)
  - wholesale_prices:    Daily wholesale TGP + international benchmarks (AIP + EIA)

Designed to match the schema in amip_data_audit.md exactly.

Usage:
  python scripts/create_schema.py            # from project root
  python create_schema.py                    # from scripts/
"""

from pathlib import Path
import duckdb

# Resolve db path relative to project root (one level up from scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "amip.duckdb"


def create_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Create all AMIP V1 tables. Idempotent — uses IF NOT EXISTS."""

    # ── stations: unified station/site reference ──────────────────────
    # Normalises NSW station reference and VIC SCATS site metadata.
    # Composite key format: {state}_{source_id} e.g. NSW_10001, VIC_S3001
    con.execute("""
        CREATE TABLE IF NOT EXISTS stations (
            station_id      VARCHAR PRIMARY KEY,
            state           VARCHAR(3)  NOT NULL,   -- NSW | VIC
            city            VARCHAR     NOT NULL,   -- Sydney | Melbourne
            source_id       VARCHAR     NOT NULL,   -- original ID from source system
            source_system   VARCHAR     NOT NULL,   -- tfnsw_permanent | tfnsw_sample | vic_scats | vic_bluetooth | vic_tirtl
            road_name       VARCHAR,
            suburb          VARCHAR,
            latitude        DOUBLE,
            longitude       DOUBLE,
            direction       VARCHAR,                -- N/S/E/W or inbound/outbound
            road_type       VARCHAR,                -- freeway | arterial | collector | local
            quality_rating  VARCHAR                 -- source data quality indicator
        );
    """)

    # ── hourly_counts: core fact table ────────────────────────────────
    # One row per station per hour. NSW maps directly (pivot from 24-col layout).
    # VIC SCATS 15-min data aggregated to hourly via SUM.
    con.execute("""
        CREATE TABLE IF NOT EXISTS hourly_counts (
            station_id      VARCHAR     NOT NULL,
            ts_hour         TIMESTAMP   NOT NULL,   -- hour start, AEST local time
            vehicle_count   INTEGER     NOT NULL,
            state           VARCHAR(3)  NOT NULL,   -- partition column: NSW | VIC
            day_of_week     TINYINT     NOT NULL,   -- 1=Mon .. 7=Sun (ISO)
            hour_of_day     TINYINT     NOT NULL,   -- 0–23, derived from ts_hour
            is_weekday      BOOLEAN     NOT NULL,   -- Mon–Fri = true

            PRIMARY KEY (station_id, ts_hour)
        );
    """)

    # Indexes for common query patterns
    con.execute("CREATE INDEX IF NOT EXISTS idx_hc_state_ts    ON hourly_counts (state, ts_hour);")
    con.execute("CREATE INDEX IF NOT EXISTS idx_hc_ts_dow      ON hourly_counts (ts_hour, day_of_week);")

    # ── bluetooth_routes: VIC Bluetooth route reference ───────────────
    # FK target for speed_observations.route_id.
    # One row per monitored freeway/arterial route in Melbourne.
    con.execute("""
        CREATE TABLE IF NOT EXISTS bluetooth_routes (
            route_id            VARCHAR PRIMARY KEY,
            route_name          VARCHAR     NOT NULL,
            primary_road_name   VARCHAR,
            start_end_desc      VARCHAR,            -- e.g. "Warrigal Rd to Toorak Rd"
            length_m            INTEGER,            -- route length in metres
            geometry_geojson    VARCHAR,            -- GeoJSON LineString coordinates
            direction           VARCHAR             -- inbound | outbound
        );
    """)

    # ── speed_observations: speed & travel time (VIC only V1) ─────────
    # Populated by polling the VIC Bluetooth API.
    # Same schema accommodates future NSW speed data.
    con.execute("""
        CREATE TABLE IF NOT EXISTS speed_observations (
            route_id            VARCHAR     NOT NULL,
            ts_interval         TIMESTAMP   NOT NULL,   -- interval start, AEST
            speed_kmh           SMALLINT,
            travel_time_sec     INTEGER,
            delay_sec           INTEGER,                -- delay vs free-flow
            congestion_index    DECIMAL(4,2),           -- std devs from expected
            data_status         VARCHAR,                -- live | insufficient_live | history_missing | closed
            route_length_m      INTEGER,                -- denormalised for query convenience

            PRIMARY KEY (route_id, ts_interval)
        );
    """)

    con.execute("CREATE INDEX IF NOT EXISTS idx_so_ts ON speed_observations (ts_interval);")

    # ── calendar: date dimension & context signals ────────────────────
    # One row per date. Pre-populated for the full data range.
    # Join to any fact table on date for contextual analysis.
    con.execute("""
        CREATE TABLE IF NOT EXISTS calendar (
            date                    DATE PRIMARY KEY,
            day_of_week             TINYINT     NOT NULL,   -- 1=Mon .. 7=Sun
            is_weekday              BOOLEAN     NOT NULL,
            week_number             TINYINT     NOT NULL,   -- ISO week
            month                   TINYINT     NOT NULL,   -- 1–12
            year                    SMALLINT    NOT NULL,
            is_public_holiday_nsw   BOOLEAN     NOT NULL DEFAULT false,
            is_public_holiday_vic   BOOLEAN     NOT NULL DEFAULT false,
            is_school_holiday_nsw   BOOLEAN     NOT NULL DEFAULT false,
            is_school_holiday_vic   BOOLEAN     NOT NULL DEFAULT false,
            event_name              VARCHAR,                -- AFL GF, Melbourne Cup, etc.
            season                  VARCHAR                 -- summer | autumn | winter | spring
        );
    """)

    # ── data_modules: manifest of active data sources ─────────────────
    # Per PROJECT_REFERENCE: manifest.json drives what modules are active.
    # This is the DB-resident equivalent — one row per ingested source.
    con.execute("""
        CREATE TABLE IF NOT EXISTS data_modules (
            module_id       VARCHAR PRIMARY KEY,     -- e.g. nsw_hourly_permanent
            display_name    VARCHAR     NOT NULL,
            source_system   VARCHAR     NOT NULL,
            state           VARCHAR(3)  NOT NULL,
            status          VARCHAR     NOT NULL DEFAULT 'pending',  -- pending | active | stale | error
            last_ingested   TIMESTAMP,
            row_count       BIGINT,
            date_range_start DATE,
            date_range_end   DATE,
            notes           VARCHAR
        );
    """)

    # ── fuel_stations: VIC fuel station reference (Servo Saver) ───────
    # Loaded from Servo Saver /fuel/reference-data/stations + /brands.
    # One row per registered fuel station in Victoria.
    con.execute("""
        CREATE TABLE IF NOT EXISTS fuel_stations (
            station_id      VARCHAR PRIMARY KEY,     -- Servo Saver fuelStation.id
            name            VARCHAR     NOT NULL,
            brand_id        VARCHAR,
            brand_name      VARCHAR,                 -- denormalised from brands endpoint
            brand_type      VARCHAR,                 -- major | independent
            address         VARCHAR,
            postcode        VARCHAR,                 -- parsed from address
            suburb          VARCHAR,                 -- parsed from address
            latitude        DOUBLE,
            longitude       DOUBLE,
            contact_phone   VARCHAR,
            updated_at      TIMESTAMP                -- last metadata update from API
        );
    """)

    # ── fuel_prices: daily retail price snapshots (Servo Saver) ───────
    # One row per station × fuel type × snapshot date.
    # Built by daily polling of /fuel/prices endpoint.
    con.execute("""
        CREATE TABLE IF NOT EXISTS fuel_prices (
            station_id      VARCHAR     NOT NULL,    -- FK to fuel_stations
            snapshot_date   DATE        NOT NULL,    -- date we polled
            fuel_type       VARCHAR     NOT NULL,    -- U91 | P95 | P98 | DSL | PDSL | E10 | E85 | B20 | LPG | LNG | CNG
            price_cpl       DECIMAL(5,1),            -- cents per litre (e.g. 188.8)
            is_available    BOOLEAN,
            retailer_updated_at TIMESTAMP,           -- when the retailer last changed this price

            PRIMARY KEY (station_id, snapshot_date, fuel_type)
        );
    """)

    con.execute("CREATE INDEX IF NOT EXISTS idx_fp_date     ON fuel_prices (snapshot_date);")
    con.execute("CREATE INDEX IF NOT EXISTS idx_fp_type     ON fuel_prices (fuel_type, snapshot_date);")

    # ── wholesale_prices: daily TGP + international benchmarks ────────
    # Seeded from AIP TGP Excel (years of history), then kept current
    # by scraping api.aip.com.au/public/tgpTables (rolling 5-day table).
    # Brent crude added via EIA API + RBA AUD/USD exchange rate.
    con.execute("""
        CREATE TABLE IF NOT EXISTS wholesale_prices (
            date            DATE PRIMARY KEY,
            mel_ulp_tgp_cpl     DECIMAL(5,1),        -- Melbourne ULP Terminal Gate Price (c/l inc GST)
            mel_diesel_tgp_cpl  DECIMAL(5,1),        -- Melbourne Diesel TGP
            syd_ulp_tgp_cpl     DECIMAL(5,1),        -- Sydney ULP TGP (for reference)
            national_ulp_tgp_cpl DECIMAL(5,1),       -- National average ULP TGP
            national_diesel_tgp_cpl DECIMAL(5,1),    -- National average Diesel TGP
            brent_usd_bbl       DECIMAL(6,2),        -- Brent crude USD per barrel (EIA)
            aud_usd_rate        DECIMAL(6,4),        -- AUD/USD exchange rate (RBA)
            brent_aud_cpl       DECIMAL(5,1)         -- Brent converted to AUD cents/litre
        );
    """)


def verify_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Print table names and column counts as a quick sanity check."""
    tables = con.execute("""
        SELECT table_name,
               (SELECT COUNT(*) FROM information_schema.columns c
                WHERE c.table_name = t.table_name) as col_count
        FROM information_schema.tables t
        WHERE table_schema = 'main'
        ORDER BY table_name;
    """).fetchall()

    print(f"\nAMIP schema created: {DB_PATH}")
    print(f"{'Table':<25} {'Columns':>7}")
    print("-" * 33)
    for name, cols in tables:
        print(f"  {name:<23} {cols:>5}")


if __name__ == "__main__":
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    create_schema(con)
    verify_schema(con)
    con.close()
