-- Cleaning layer. Every analysis query reads from clean_orders, never the raw feed.
--   1. Remove exact duplicate events (scanner double-reads).
--   2. Drop orders with a missing pack scan (cycle time can't be measured).
--   3. Drop clock-skew rows where pick starts before the order exists.
-- Then derive the fields the business questions need.

CREATE OR REPLACE VIEW clean_orders AS
WITH deduped AS (
    SELECT DISTINCT * FROM raw_order_events
)
SELECT
    d.*,
    s.city,
    s.state,
    CAST(d.order_ts AS DATE)                                   AS order_date,
    HOUR(d.order_ts)                                           AS order_hour,
    DAYNAME(d.order_ts)                                        AS order_dow,
    ISODOW(d.order_ts) >= 6                                    AS is_weekend,
    CASE WHEN HOUR(d.order_ts) BETWEEN 6 AND 17 THEN 'Day' ELSE 'Night' END AS shift,
    -- Stage durations in minutes
    DATE_DIFF('second', d.order_ts,      d.pick_start_ts) / 60.0 AS queue_min,
    DATE_DIFF('second', d.pick_start_ts, d.pick_end_ts)   / 60.0 AS pick_min,
    DATE_DIFF('second', d.pick_end_ts,   d.pack_end_ts)   / 60.0 AS pack_min,
    DATE_DIFF('second', d.pack_end_ts,   d.ship_ts)       / 60.0 AS dock_wait_min,
    DATE_DIFF('second', d.order_ts,      d.ship_ts)       / 3600.0 AS cycle_hours,
    d.ship_ts > d.promised_ship_ts                             AS sla_breach
FROM deduped d
JOIN sites s USING (site_id)
WHERE d.pack_end_ts IS NOT NULL
  AND d.pick_start_ts >= d.order_ts;
