-- Flowmetrics business questions.
-- Run with: duckdb data/processed/flowmetrics.duckdb < sql/analysis.sql

CREATE OR REPLACE TABLE orders AS
SELECT * FROM read_csv_auto('data/raw/orders.csv', header = true, timestampformat = '%Y-%m-%d %H:%M:%S%z');

CREATE OR REPLACE TABLE fulfillment_events AS
SELECT * FROM read_csv_auto('data/raw/fulfillment_events.csv', header = true, timestampformat = '%Y-%m-%d %H:%M:%S%z');

-- 1. Where are the bottlenecks?
WITH stage_times AS (
    SELECT order_id,
        datediff('minute', min(event_ts) FILTER (event_type = 'order_created'), min(event_ts) FILTER (event_type = 'picked')) / 60.0 AS create_to_pick_hours,
        datediff('minute', min(event_ts) FILTER (event_type = 'picked'), min(event_ts) FILTER (event_type = 'packed')) / 60.0 AS pick_to_pack_hours,
        datediff('minute', min(event_ts) FILTER (event_type = 'packed'), min(event_ts) FILTER (event_type = 'shipped')) / 60.0 AS pack_to_ship_hours,
        datediff('minute', min(event_ts) FILTER (event_type = 'shipped'), min(event_ts) FILTER (event_type = 'delivered')) / 60.0 AS ship_to_delivery_hours
    FROM fulfillment_events
    GROUP BY order_id
)
SELECT round(avg(create_to_pick_hours), 2) AS create_to_pick_hours,
       round(avg(pick_to_pack_hours), 2) AS pick_to_pack_hours,
       round(avg(pack_to_ship_hours), 2) AS pack_to_ship_hours,
       round(avg(ship_to_delivery_hours), 2) AS ship_to_delivery_hours
FROM stage_times;

-- 2. Which sites breach SLA most?
SELECT site_id,
       count(*) AS orders,
       round(avg(process_hours), 2) AS avg_process_hours,
       round(100 * avg(CASE WHEN delivery_ts > promised_delivery_ts THEN 1 ELSE 0 END), 1) AS sla_breach_pct,
       round(avg(datediff('minute', order_ts, delivery_ts) / 24.0 / 60.0), 2) AS avg_order_to_delivery_days
FROM orders
GROUP BY site_id
ORDER BY sla_breach_pct DESC;

-- 3. What drives latency?
SELECT priority, channel, item_count,
       count(*) AS orders,
       round(avg(process_hours), 2) AS avg_process_hours,
       round(100 * avg(CASE WHEN delivery_ts > promised_delivery_ts THEN 1 ELSE 0 END), 1) AS sla_breach_pct
FROM orders
GROUP BY ALL
ORDER BY avg_process_hours DESC
LIMIT 25;

-- 4. What are peak-hour throughput patterns?
SELECT date_part('hour', order_ts) AS order_hour,
       count(*) AS orders,
       round(count(*) / 90.0, 1) AS avg_orders_per_day,
       round(avg(process_hours), 2) AS avg_process_hours
FROM orders
GROUP BY order_hour
ORDER BY order_hour;

-- 5. Executive KPI summary.
SELECT count(*) AS total_orders,
       round(avg(process_hours), 2) AS avg_process_hours,
       round(median(process_hours), 2) AS median_process_hours,
       round(100 * avg(CASE WHEN delivery_ts > promised_delivery_ts THEN 1 ELSE 0 END), 1) AS overall_sla_breach_pct,
       round(100 * avg(CASE WHEN priority = 'Priority' THEN 1 ELSE 0 END), 1) AS priority_mix_pct
FROM orders;
