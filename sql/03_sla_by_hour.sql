-- Q3. When during the day do breaches happen? (Priority vs. Standard, by order hour)

SELECT
    order_hour,
    service_tier,
    COUNT(*)                                                       AS orders,
    ROUND(100.0 * AVG(CASE WHEN sla_breach THEN 1 ELSE 0 END), 2)  AS breach_rate_pct,
    ROUND(MEDIAN(queue_min), 1)                                    AS median_queue_min,
    ROUND(MEDIAN(cycle_hours), 2)                                  AS median_cycle_hours
FROM clean_orders
GROUP BY order_hour, service_tier
ORDER BY service_tier, order_hour;
