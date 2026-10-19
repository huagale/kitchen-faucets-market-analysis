-- Несколько строк на бренд+наименование+месяц: кандидаты для проверки, не полные дубли.
-- Исходные строки не удаляются и не схлопываются при загрузке.
SELECT product_id, brand_name, article_name, month, COUNT(*) AS source_rows,
       SUM(revenue) AS revenue_rub, SUM(quantity) AS units_sold,
       COUNT(DISTINCT color_final) AS color_variants,
       COUNT(DISTINCT metal_final) AS material_variants,
       COUNT(DISTINCT subcategory) AS subcategory_variants
FROM v_sales
WHERE month BETWEEN :date_from AND :date_to
  AND (:brand IS NULL OR brand_name = :brand)
GROUP BY product_id, brand_name, article_name, month
HAVING COUNT(*) > 1
ORDER BY source_rows DESC, brand_name, article_name, month
LIMIT :limit;
