import duckdb, os, sys
from pathlib import Path

FRESH = "db/amip_compact.duckdb"
EXPORT = Path("db/amip_export")

con = duckdb.connect(FRESH, config={"memory_limit": "2GB", "threads": 2})
con.execute("SET preserve_insertion_order=false")

# Schema (no indexes yet)
for stmt in (EXPORT / "schema.sql").read_text().split(";;"):
    s = stmt.strip()
    if s and not s.upper().startswith("CREATE INDEX"):
        try:
            con.execute(s)
        except:
            pass

# Load all tables EXCEPT hourly_counts
for pq in sorted(EXPORT.glob("*.parquet")):
    t = pq.stem
    if t == "hourly_counts":
        continue
    sys.stdout.write(f"  {t}...")
    sys.stdout.flush()
    con.execute(f"INSERT INTO \"{t}\" SELECT * FROM read_parquet('{pq}')")
    n = con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
    sys.stdout.write(f" {n:,}\n")
    sys.stdout.flush()
con.execute("CHECKPOINT")

# Load hourly_counts in monthly chunks to stay within memory
pq = str(EXPORT / "hourly_counts.parquet")
sys.stdout.write("  hourly_counts (chunked)...\n")
sys.stdout.flush()
total = 0
for year in [2024, 2025, 2026]:
    for month in range(1, 13):
        start = f"{year}-{month:02d}-01"
        if month == 12:
            end = f"{year+1}-01-01"
        else:
            end = f"{year}-{month+1:02d}-01"
        con.execute(f"""
            INSERT INTO hourly_counts
            SELECT * FROM read_parquet('{pq}')
            WHERE ts_hour >= '{start}'::TIMESTAMP
              AND ts_hour < '{end}'::TIMESTAMP
        """)
        n = con.execute(f"""
            SELECT count(*) FROM hourly_counts
            WHERE ts_hour >= '{start}'::TIMESTAMP
              AND ts_hour < '{end}'::TIMESTAMP
        """).fetchone()[0]
        total += n
        if n > 0:
            sys.stdout.write(f"    {start[:7]}: {n:,}\n")
            sys.stdout.flush()
        con.execute("CHECKPOINT")
        if year == 2026 and month >= 4:
            break
    if year == 2026:
        break

sys.stdout.write(f"  hourly_counts total: {total:,}\n")
sys.stdout.flush()

# Indexes
sys.stdout.write("  Creating indexes...\n")
sys.stdout.flush()
for stmt in (EXPORT / "schema.sql").read_text().split(";;"):
    s = stmt.strip()
    if s and s.upper().startswith("CREATE INDEX"):
        try:
            con.execute(s)
        except:
            pass
con.execute("FORCE CHECKPOINT")
con.close()

size = os.path.getsize(FRESH) / (1024**2)
sys.stdout.write(f"\nDone: {size:.0f} MB\n")
sys.stdout.write("COMPACT_COMPLETE\n")
sys.stdout.flush()
