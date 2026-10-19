-- Каталог бренд+наименование с объяснимой разметкой. По умолчанию первые 1000 строк.
-- Для неоднозначных характеристик не выбираем произвольное значение.
WITH catalog AS (
    SELECT product_id, brand_name, article_name, category,
           CASE WHEN COUNT(DISTINCT subcategory) = 1 AND COUNT(rule_id) = COUNT(*)
                THEN MIN(subcategory) ELSE 'Требует проверки' END AS subcategory,
           CASE WHEN COUNT(DISTINCT rule_id) = 1 THEN MIN(rule_id) END AS rule_id,
           CASE WHEN COUNT(DISTINCT color_final) = 1 THEN MIN(color_final) END AS color,
           CASE WHEN COUNT(DISTINCT metal_final) = 1 THEN MIN(metal_final) END AS material_or_finish,
           CASE WHEN COUNT(DISTINCT product_type) = 1 THEN MIN(product_type) END AS mechanism,
           COUNT(*) AS source_rows, MIN(month) AS first_month, MAX(month) AS last_month,
           SUM(revenue) AS revenue_rub, SUM(quantity) AS units_sold,
           CASE WHEN MAX(requires_review) = 1 OR COUNT(DISTINCT subcategory) > 1
                       OR COUNT(DISTINCT color_final) > 1 OR COUNT(DISTINCT metal_final) > 1
                       OR COUNT(DISTINCT product_type) > 1
                THEN 'needs_review' ELSE 'rule_assigned' END AS review_status
    FROM v_sales
    WHERE month BETWEEN :date_from AND :date_to
      AND (:brand IS NULL OR brand_name = :brand)
    GROUP BY product_id, brand_name, article_name, category
)
SELECT * FROM catalog
ORDER BY brand_name, article_name, product_id
LIMIT :limit;
