-- Сравнение с предыдущим календарным годом внутри выбранного среза.
-- Если в срезе нет предыдущего года, динамика NULL, а не 0%.
WITH annual AS (
    SELECT brand_name, year, SUM(revenue) AS revenue_rub, SUM(quantity) AS units_sold
    FROM v_sales
    WHERE month BETWEEN :date_from AND :date_to
      AND (:brand IS NULL OR brand_name = :brand)
    GROUP BY brand_name, year
)
SELECT curr.brand_name, curr.year, curr.revenue_rub,
       prev.revenue_rub AS previous_year_revenue_rub,
       CASE WHEN prev.revenue_rub > 0
            THEN ROUND(100.0 * (curr.revenue_rub - prev.revenue_rub) / prev.revenue_rub, 2)
       END AS revenue_growth_pct,
       curr.units_sold, prev.units_sold AS previous_year_units
FROM annual AS curr
LEFT JOIN annual AS prev ON prev.brand_name = curr.brand_name AND prev.year = curr.year - 1
ORDER BY curr.year DESC, curr.revenue_rub DESC, curr.brand_name;
