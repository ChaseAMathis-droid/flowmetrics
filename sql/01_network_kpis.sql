-- Q1. How is the network performing overall, by service tier?

SELECT
    service_tier,
    COUNT(*)                                        AS orders,
    SUM(units)                                      AS units,
    ROUND(AVG(cycle_hours), 2)                      AS avg_cycle_hours,
    ROUND(MEDIAN(cycle_hours), 2)                   AS median_cycle_hours,
    ROUND(QUANTILE_CONT(cycle_hours, 0.95), 2)      AS p95_cycle_hours,
    ANY_VALUE(sla_hours)                            AS sla_hours,
    SUM(CASE WHEN sla_breach THEN 1 ELSE 0 END)     AS breaches,
    ROUND(100.0 * AVG(CASE WHEN sla_breach THEN 1 ELSE 0 END), 2) AS breach_rate_pct
FROM clean_orders
GROUP BY service_tier
ORDER BY service_tier;
