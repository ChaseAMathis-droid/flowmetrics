-- Q0. How clean is the raw event feed?
-- Profiles the defects that must be handled before any KPI is trustworthy.

WITH dupes AS (
    SELECT order_id, COUNT(*) - 1 AS extra_rows
    FROM raw_order_events
    GROUP BY order_id
    HAVING COUNT(*) > 1
)
SELECT 'Total raw rows'                       AS check_name, COUNT(*) AS row_count FROM raw_order_events
UNION ALL
SELECT 'Duplicate rows (scanner double-reads)', CAST(COALESCE(SUM(extra_rows), 0) AS BIGINT) FROM dupes
UNION ALL
SELECT 'Missing pack scan',                     COUNT(*) FROM raw_order_events WHERE pack_end_ts IS NULL
UNION ALL
SELECT 'Clock skew (pick before order)',       COUNT(*) FROM raw_order_events WHERE pick_start_ts < order_ts
UNION ALL
SELECT 'Rows kept after cleaning',             COUNT(*) FROM clean_orders;
