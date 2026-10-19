-- Диагностика полноты описаний и согласованности признаков.
-- Пропуск характеристики сам по себе не доказывает ошибку товара.
WITH scoped AS (
    SELECT * FROM v_sales
    WHERE month BETWEEN :date_from AND :date_to
      AND (:brand IS NULL OR brand_name = :brand)
), checks AS (
    SELECT 'missing_color' AS metric, 'Не определён цвет' AS description,
           COUNT(*) AS total_rows, COALESCE(SUM(color_final IS NULL), 0) AS affected_rows FROM scoped
    UNION ALL SELECT 'missing_material', 'Не определён материал или покрытие',
           COUNT(*), COALESCE(SUM(metal_final IS NULL), 0) FROM scoped
    UNION ALL SELECT 'unknown_mechanism', 'Тип механизма не определён',
           COUNT(*), COALESCE(SUM(product_type IS NULL OR product_type = 'не определен'), 0) FROM scoped
    UNION ALL SELECT 'missing_original_filter_label', 'Исходная cat3 не заполнена',
           COUNT(*), COALESCE(SUM(raw_filter_label IS NULL), 0) FROM scoped
    UNION ALL SELECT 'filter_label_conflict', 'Исходная cat3 расходится с cat3_new',
           COUNT(*), COALESCE(SUM(raw_filter_label IS NOT NULL AND raw_filter_label <> filter_label), 0) FROM scoped
    UNION ALL SELECT 'unmatched_rule', 'Не найдено правило подкатегории',
           COUNT(*), COALESCE(SUM(rule_id IS NULL), 0) FROM scoped
    UNION ALL SELECT 'discount_marked', 'В исходных признаках отмечена уценка',
           COUNT(*), COALESCE(SUM(is_discounted), 0) FROM scoped
)
SELECT metric, description, total_rows, affected_rows,
       ROUND(100.0 * affected_rows / NULLIF(total_rows, 0), 4) AS affected_pct
FROM checks
ORDER BY metric;
