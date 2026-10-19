-- Помесячная динамика. Средняя цена взвешена проданным количеством.
SELECT month,
       COUNT(*) AS source_rows,
       COUNT(DISTINCT product_id) AS active_product_keys,
       COUNT(DISTINCT brand_name) AS active_brands,
       SUM(revenue) AS revenue_rub,
       SUM(quantity) AS units_sold,
       ROUND(1.0 * SUM(revenue) / NULLIF(SUM(quantity), 0), 2) AS weighted_price_rub
FROM v_sales
WHERE month BETWEEN :date_from AND :date_to
  AND (:brand IS NULL OR brand_name = :brand)
GROUP BY month
ORDER BY month;
