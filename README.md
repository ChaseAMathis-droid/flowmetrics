# Flowmetrics: fulfillment bottleneck case study

## Executive summary

This case study analyzes a deterministic synthetic fulfillment network with **120,000 orders and 600,000 event records** across five sites and 90 days. The network averages **8.44 hours of fulfillment processing**, with a **22.7% delivery-SLA breach rate**. The largest elapsed interval is shipping to delivery (**31.95 hours**), followed by packing to shipping (**3.63 hours**).

The clearest site signal is **PHL**, with a 24.5% breach rate and 9.81 average process hours, while ATL is the fastest and lowest-breach site at 7.04 hours and 21.0%. Priority orders are intentionally time-sensitive: they average 7.02 process hours but breach their 24-hour commitment 91.3% of the time, versus 2.2% for standard orders. Volume is concentrated around **08:00, 12:00, and 13:00**, making those windows the first candidates for capacity planning.

Recommended actions are to investigate the post-shipment carrier/last-mile interval, run a focused PHL staffing and handoff review, and protect priority-order capacity during the busiest hours. These findings are generated from the reproducible pipeline below rather than hard-coded into the analysis.

**Tableau Public dashboard:** publish the generated `outputs/tableau_orders.csv` using the specification in [`dashboard/DASHBOARD_SPEC.md`](dashboard/DASHBOARD_SPEC.md), then add the public URL here.

## Questions answered

1. Where are the bottlenecks between order creation, picking, packing, shipping, and delivery?
2. Which fulfillment sites breach their SLA most often?
3. How do priority, channel, and item count relate to latency?
4. What hours create peak throughput pressure?
5. What are the network-level volume, latency, and SLA KPIs?

## Data

`scripts/generate_data.py` creates:

- `data/raw/orders.csv`: one row per order with site, region, channel, priority, item count, timestamps, SLA target, and processing duration.
- `data/raw/fulfillment_events.csv`: five timestamped lifecycle events per order.

The data is synthetic and contains no customer or personally identifiable information. The generator uses seed `42`, modeled site effects, order complexity, priority mix, weekday/weekend load, and intraday peaks so that the analysis has realistic operational variation without pretending to represent a real company.

## Methods

- **Generation:** NumPy/Pandas with a fixed seed and explicit assumptions.
- **Storage and SQL:** DuckDB tables loaded from CSV; queries live in [`sql/analysis.sql`](sql/analysis.sql).
- **Cleaning and analysis:** [`notebooks/fulfillment_analysis.ipynb`](notebooks/fulfillment_analysis.ipynb) parses timestamps, checks uniqueness and chronology, derives SLA breach flags, and produces summary tables and charts.
- **Dashboard extract:** `scripts/build_analysis.py` adds Tableau-friendly calculated columns and writes `outputs/tableau_orders.csv`.

## Reproduce

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_data.py
python scripts/build_analysis.py
jupyter notebook notebooks/fulfillment_analysis.ipynb
```

To run the SQL file directly:

```bash
duckdb data/processed/flowmetrics.duckdb < sql/analysis.sql
```

See [`dashboard/DASHBOARD_SPEC.md`](dashboard/DASHBOARD_SPEC.md) for the Tableau Public story, calculated fields, and publishing checklist.
