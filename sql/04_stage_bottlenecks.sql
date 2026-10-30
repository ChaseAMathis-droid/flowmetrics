-- Q4. Which process stage is the bottleneck, and where?
-- Median minutes spent in each stage, by site and shift, compared with the network median.

WITH stage AS (
    SELECT
        site_id, city, shift,
        COUNT(*)                   AS orders,
        MEDIAN(queue_min)          AS queue_min,
        MEDIAN(pick_min)           AS pick_min,
        MEDIAN(pack_min)           AS pack_min,
        MEDIAN(dock_wait_min)      AS dock_wait_min
    FROM clean_orders
    GROUP BY site_id, city, shift
),
network AS (
    SELECT shift, MEDIAN(pack_min) AS net_pack_min, MEDIAN(queue_min) AS net_queue_min
    FROM clean_orders
    GROUP BY shift
)
SELECT
    s.site_id, s.city, s.shift, s.orders,
    ROUND(s.queue_min, 1)                    AS median_queue_min,
    ROUND(s.pick_min, 1)                     AS median_pick_min,
    ROUND(s.pack_min, 1)                     AS median_pack_min,
    ROUND(s.dock_wait_min, 1)                AS median_dock_wait_min,
    ROUND(s.pack_min / n.net_pack_min, 2)    AS pack_vs_network_x,
    ROUND(s.queue_min / n.net_queue_min, 2)  AS queue_vs_network_x
FROM stage s
JOIN network n USING (shift)
ORDER BY pack_vs_network_x DESC;
