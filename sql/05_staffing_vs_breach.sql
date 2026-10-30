-- Q5. Does labor explain the breaches?
-- Joins the staffing plan to order outcomes at the site/day/shift grain.

WITH outcomes AS (
    SELECT
        site_id, order_date AS date, shift, is_weekend,
        COUNT(*)                                          AS orders,
        SUM(units) * 10                                   AS est_units,   -- data is a 1-in-10 sample
        AVG(CASE WHEN sla_breach THEN 1.0 ELSE 0 END)     AS breach_rate
    FROM clean_orders
    GROUP BY site_id, order_date, shift, is_weekend
),
joined AS (
    SELECT
        o.*,
        st.planned_headcount,
        st.actual_headcount,
        st.actual_headcount * 1.0 / st.planned_headcount AS attendance_rate,
        o.est_units * 1.0 / NULLIF(st.actual_headcount, 0) AS units_per_head
    FROM outcomes o
    JOIN staffing st USING (site_id, date, shift)
)
SELECT
    shift,
    CASE WHEN is_weekend THEN 'Weekend' ELSE 'Weekday' END              AS day_type,
    CASE WHEN attendance_rate < 0.88 THEN 'Call-out day (<88%)' ELSE 'Normal attendance' END AS attendance_band,
    COUNT(*)                                                             AS site_shifts,
    ROUND(AVG(planned_headcount), 1)                                     AS avg_planned_hc,
    ROUND(AVG(units_per_head), 0)                                        AS avg_units_per_head,
    ROUND(100 * AVG(breach_rate), 2)                                     AS avg_breach_rate_pct
FROM joined
GROUP BY ALL
ORDER BY shift, day_type, attendance_band;
