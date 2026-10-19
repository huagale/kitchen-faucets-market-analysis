-- ABC по накопленной доле <=80%, <=95%, >95% — как в исходном проекте.
-- Бренд, пересекающий порог, относится к следующей группе.
WITH totals AS (
    SELECT brand_name, SUM(revenue) AS revenue_rub
    FROM v_sales
    WHERE month BETWEEN :date_from AND :date_to
      AND (:brand IS NULL OR brand_name = :brand)
    GROUP BY brand_name
), shares AS (
    SELECT *, 1.0 * revenue_rub / NULLIF(SUM(revenue_rub) OVER (), 0) AS share,
           1.0 * SUM(revenue_rub) OVER (
               ORDER BY revenue_rub DESC, brand_name
               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
           ) / NULLIF(SUM(revenue_rub) OVER (), 0) AS cumulative_share
    FROM totals
)
SELECT brand_name, revenue_rub, ROUND(share * 100, 4) AS revenue_share_pct,
       ROUND(cumulative_share * 100, 4) AS cumulative_share_pct,
       CASE WHEN cumulative_share <= 0.80 THEN 'A'
            WHEN cumulative_share <= 0.95 THEN 'B' ELSE 'C' END AS abc_group
FROM shares
ORDER BY revenue_rub DESC, brand_name;
