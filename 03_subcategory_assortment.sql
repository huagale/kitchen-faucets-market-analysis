-- Учебные подкатегории по исходным признакам cat3_new и has_pullout.
-- Неотмеченный признак не означает фактическое отсутствие функции.
SELECT COALESCE(rule_id, 'REVIEW') AS rule_id,
       COALESCE(subcategory, 'Требует проверки') AS subcategory,
       COUNT(*) AS source_rows, COUNT(DISTINCT product_id) AS product_keys,
       SUM(revenue) AS revenue_rub, SUM(quantity) AS units_sold,
       ROUND(100.0 * SUM(revenue) / NULLIF(SUM(SUM(revenue)) OVER (), 0), 3) AS revenue_share_pct,
       SUM(requires_review) AS rows_to_review
FROM v_sales
WHERE month BETWEEN :date_from AND :date_to
  AND (:brand IS NULL OR brand_name = :brand)
GROUP BY rule_id, subcategory
ORDER BY rule_id;
