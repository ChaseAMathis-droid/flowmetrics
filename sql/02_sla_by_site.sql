-- Q2. Which sites breach SLA most, and how far are they from the network?

WITH site AS (
    SELECT
        site_id, city, state,
        COUNT(*)                                                  AS orders,
        SUM(CASE WHEN sla_breach THEN 1 ELSE 0 END)               AS breaches,
        AVG(CASE WHEN sla_breach THEN 1.0 ELSE 0 END)             AS breach_rate,
        AVG(CASE WHEN service_tier = 'Priority'
                 THEN CASE WHEN sla_breach THEN 1.0 ELSE 0 END END) AS priority_breach_rate,
        MEDIAN(cycle_hours)                                       AS median_cycle_hours
    FROM clean_orders
    GROUP BY site_id, city, state
),
network AS (
    SELECT AVG(CASE WHEN sla_breach THEN 1.0 ELSE 0 END) AS net_rate FROM clean_orders
)
SELECT
    site_id, city, state, orders, breaches,
    ROUND(100 * breach_rate, 2)                         AS breach_rate_pct,
    ROUND(100 * priority_breach_rate, 2)                AS priority_breach_rate_pct,
    ROUND(breach_rate / net_rate, 2)                    AS vs_network_x,
    ROUND(median_cycle_hours, 2)                        AS median_cycle_hours,
    RANK() OVER (ORDER BY breach_rate DESC)             AS breach_rank
FROM site CROSS JOIN network
ORDER BY breach_rank;
