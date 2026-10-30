-- Q6. Daily trend by site, with anomaly flags.
-- A site-day is flagged when its breach rate OR its median cycle time is more than
-- 3 standard deviations above that site's own 31-day average. This catches one-off
-- incidents (equipment outages, bad call-out days) that monthly averages hide.

WITH daily AS (
    SELECT
        site_id, city, order_date,
        COUNT(*)                                         AS orders,
        AVG(CASE WHEN sla_breach THEN 1.0 ELSE 0 END)    AS breach_rate,
        MEDIAN(cycle_hours)                              AS median_cycle_hours
    FROM clean_orders
    GROUP BY site_id, city, order_date
),
scored AS (
    SELECT
        *,
        (breach_rate - AVG(breach_rate) OVER w) / NULLIF(STDDEV(breach_rate) OVER w, 0)                 AS breach_z,
        (median_cycle_hours - AVG(median_cycle_hours) OVER w) / NULLIF(STDDEV(median_cycle_hours) OVER w, 0) AS cycle_z
    FROM daily
    WINDOW w AS (PARTITION BY site_id)
)
SELECT
    site_id, city, order_date, orders,
    ROUND(100 * breach_rate, 2)       AS breach_rate_pct,
    ROUND(median_cycle_hours, 2)      AS median_cycle_hours,
    ROUND(breach_z, 2)                AS breach_z,
    ROUND(cycle_z, 2)                 AS cycle_time_z,
    breach_z > 3 OR cycle_z > 3       AS is_anomaly
FROM scored
ORDER BY site_id, order_date;
