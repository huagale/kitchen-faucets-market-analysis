-- Сохранены исторические квартильные сегменты исходного Python-анализа.
-- Один product_id может встречаться в нескольких сегментах и периодах.
SELECT price_segment, COUNT(*) AS source_rows,
       COUNT(DISTINCT product_id) AS product_keys,
       SUM(revenue) AS revenue_rub, SUM(quantity) AS units_sold,
       ROUND(100.0 * SUM(revenue) / NULLIF(SUM(SUM(revenue)) OVER (), 0), 3) AS revenue_share_pct,
       ROUND(1.0 * SUM(revenue) / NULLIF(SUM(quantity), 0), 2) AS weighted_price_rub
FROM v_sales
WHERE month BETWEEN :date_from AND :date_to
  AND (:brand IS NULL OR brand_name = :brand)
GROUP BY price_segment
ORDER BY CASE price_segment WHEN 'Бюджетный' THEN 1 WHEN 'Средний' THEN 2
                           WHEN 'Премиум' THEN 3 WHEN 'Люкс' THEN 4 ELSE 5 END;
