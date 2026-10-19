-- Выручка, ширина проданного ассортимента и доля бренда в выбранном срезе.
WITH brand_totals AS (
    SELECT brand_name, COUNT(DISTINCT product_id) AS product_keys,
           COUNT(DISTINCT month) AS active_months,
           SUM(revenue) AS revenue_rub, SUM(quantity) AS units_sold
    FROM v_sales
    WHERE month BETWEEN :date_from AND :date_to
      AND (:brand IS NULL OR brand_name = :brand)
    GROUP BY brand_name
)
SELECT brand_name, product_keys, active_months, revenue_rub, units_sold,
       ROUND(100.0 * revenue_rub / NULLIF(SUM(revenue_rub) OVER (), 0), 3) AS revenue_share_pct,
       ROUND(1.0 * revenue_rub / NULLIF(units_sold, 0), 2) AS weighted_price_rub,
       ROUND(1.0 * revenue_rub / NULLIF(product_keys, 0), 2) AS revenue_per_product_key_rub
FROM brand_totals
ORDER BY revenue_rub DESC, brand_name;
