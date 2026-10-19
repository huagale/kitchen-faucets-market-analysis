-- Очередь проверки: расхождение источников или разные признаки одного технического ключа.
-- Строки не исправляются автоматически; решение остаётся за аналитиком.
SELECT product_id, brand_name, article_name,
       COUNT(*) AS source_rows,
       COUNT(DISTINCT subcategory) AS subcategory_variants,
       COUNT(DISTINCT color_final) AS color_variants,
       COUNT(DISTINCT metal_final) AS material_variants,
       COUNT(DISTINCT product_type) AS mechanism_variants,
       SUM(CASE WHEN raw_filter_label IS NOT NULL AND raw_filter_label <> filter_label THEN 1 ELSE 0 END) AS filter_conflict_rows,
       SUM(CASE WHEN rule_id IS NULL THEN 1 ELSE 0 END) AS unmatched_rule_rows,
       SUM(revenue) AS revenue_rub
FROM v_sales
WHERE month BETWEEN :date_from AND :date_to
  AND (:brand IS NULL OR brand_name = :brand)
GROUP BY product_id, brand_name, article_name
HAVING MAX(requires_review) = 1 OR COUNT(DISTINCT subcategory) > 1
       OR COUNT(DISTINCT color_final) > 1 OR COUNT(DISTINCT metal_final) > 1
       OR COUNT(DISTINCT product_type) > 1
ORDER BY filter_conflict_rows DESC, unmatched_rule_rows DESC, revenue_rub DESC, product_id
LIMIT :limit;
