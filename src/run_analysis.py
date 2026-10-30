"""
Load the raw data into DuckDB, build the cleaning layer, run every query in sql/,
and save each result to data/processed/ as a CSV (these are also the Tableau sources).

Usage:
    python src/run_analysis.py
"""

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
SQL = ROOT / "sql"


def connect() -> duckdb.DuckDBPyConnection:
    """Open an in-memory DuckDB with raw tables and the clean_orders view registered."""
    con = duckdb.connect()
    con.execute(f"""
        CREATE TABLE raw_order_events AS
        SELECT * FROM read_csv('{RAW / "order_events.csv.gz"}', header=true,
            types={{'order_ts':'TIMESTAMP','pick_start_ts':'TIMESTAMP','pick_end_ts':'TIMESTAMP',
                    'pack_end_ts':'TIMESTAMP','ship_ts':'TIMESTAMP','promised_ship_ts':'TIMESTAMP'}});
    """)
    con.execute(f"CREATE TABLE sites    AS SELECT * FROM read_csv('{RAW / 'sites.csv'}', header=true)")
    con.execute(f"CREATE TABLE staffing AS SELECT * FROM read_csv('{RAW / 'staffing.csv'}', header=true)")
    con.execute((SQL / "clean_orders.sql").read_text())
    return con


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = connect()
    for path in sorted(SQL.glob("0*.sql")):
        df = con.execute(path.read_text()).df()
        name = path.stem
        df.to_csv(OUT / f"{name}.csv", index=False)
        print(f"\n=== {name} ({len(df)} rows) ===")
        print(df.head(12).to_string(index=False))

    # Tableau extract: one row per site / date / hour / tier. Small enough for GitHub,
    # detailed enough to rebuild every chart (filters by site, day, hour, tier, shift).
    con.execute(f"""
        COPY (
            SELECT site_id, city, state, order_date, order_dow, is_weekend, order_hour, shift,
                   service_tier,
                   COUNT(*)                                        AS orders,
                   SUM(units)                                      AS units,
                   SUM(CASE WHEN sla_breach THEN 1 ELSE 0 END)     AS breaches,
                   ROUND(AVG(queue_min), 2)                        AS avg_queue_min,
                   ROUND(AVG(pick_min), 2)                         AS avg_pick_min,
                   ROUND(AVG(pack_min), 2)                         AS avg_pack_min,
                   ROUND(AVG(dock_wait_min), 2)                    AS avg_dock_wait_min,
                   ROUND(AVG(cycle_hours), 3)                      AS avg_cycle_hours
            FROM clean_orders
            GROUP BY ALL
            ORDER BY site_id, order_date, order_hour, service_tier
        ) TO '{OUT / "tableau_extract.csv"}' (HEADER, DELIMITER ',');
    """)
    print(f"\nWrote results to {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
