"""Create a DuckDB database and Tableau-ready order extract."""

from pathlib import Path
import duckdb


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "outputs"
DB = ROOT / "data" / "processed" / "flowmetrics.duckdb"


def main() -> None:
    if not (RAW / "orders.csv").exists():
        raise FileNotFoundError("Run scripts/generate_data.py first.")
    DB.parent.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB))
    con.execute(f"""
        CREATE OR REPLACE TABLE orders AS
        SELECT * FROM read_csv_auto('{RAW / "orders.csv"}', header=true);
    """)
    con.execute(f"""
        CREATE OR REPLACE TABLE fulfillment_events AS
        SELECT * FROM read_csv_auto('{RAW / "fulfillment_events.csv"}', header=true);
    """)
    con.execute(f"""
        COPY (
            SELECT *, date_part('hour', order_ts) AS order_hour,
                CASE WHEN delivery_ts > promised_delivery_ts THEN 1 ELSE 0 END AS sla_breach,
                datediff('minute', order_ts, delivery_ts) / 60.0 AS order_to_delivery_hours
            FROM orders
        ) TO '{OUT / "tableau_orders.csv"}' (HEADER, DELIMITER ',');
    """)
    print(f"Built {DB} and {OUT / 'tableau_orders.csv'}")


if __name__ == "__main__":
    main()
