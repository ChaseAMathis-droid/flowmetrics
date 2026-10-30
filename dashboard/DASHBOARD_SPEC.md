# Tableau Public dashboard specification

Publish `outputs/tableau_orders.csv` as the data source. The generated extract is
one row per order and is intentionally Tableau-friendly.

## Story layout

1. **Executive overview** — KPI cards for total orders, median process hours,
   SLA breach rate, and average daily throughput. Add a site-level breach-rate
   bar chart with a reference line for the network average.
2. **Bottleneck diagnostics** — stacked bars for average hours by fulfillment
   stage, split by site. Add a heatmap of order hour versus site for volume.
3. **Driver analysis** — scatter plot of item count versus process hours,
   colored by priority, with a trend line; add filters for site, channel, and
   priority.

## Recommended calculated fields

- `SLA Breach`: `IF [delivery_ts] > [promised_delivery_ts] THEN 1 ELSE 0 END`
- `SLA Breach Rate`: `AVG([SLA Breach])`
- `Order Hour`: `DATEPART('hour', [order_ts])`
- `Order-to-delivery hours`: `DATEDIFF('hour', [order_ts], [delivery_ts])`

## Publishing checklist

1. Run `python scripts/generate_data.py` and `python scripts/build_analysis.py`.
2. Open `outputs/tableau_orders.csv` in Tableau Public.
3. Build the three views above, add the listed filters, and publish.
4. Paste the resulting public URL into the README's Tableau link.
