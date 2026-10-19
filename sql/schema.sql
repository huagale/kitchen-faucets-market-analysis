-- SQLite 3.25+. Одна строка sales = одна исходная строка месячной статистики.
-- product_id — технический ключ (brand_clean, article_name), не артикул площадки.
PRAGMA foreign_keys = ON;

CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE brands (
    brand_id INTEGER PRIMARY KEY,
    brand_name TEXT NOT NULL UNIQUE
);
CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    brand_id INTEGER NOT NULL REFERENCES brands(brand_id),
    article_name TEXT NOT NULL,
    UNIQUE (brand_id, article_name)
);
CREATE TABLE classification_rules (
    rule_id TEXT PRIMARY KEY,
    filter_label TEXT NOT NULL,
    has_pullout INTEGER NOT NULL CHECK (has_pullout IN (0, 1)),
    subcategory TEXT NOT NULL,
    explanation TEXT NOT NULL,
    UNIQUE (filter_label, has_pullout)
);
CREATE TABLE sales (
    record_id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    month TEXT NOT NULL,
    revenue INTEGER NOT NULL CHECK (revenue >= 0),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    price REAL NOT NULL CHECK (price >= 0),
    price_segment TEXT NOT NULL,
    raw_filter_label TEXT,
    filter_label TEXT,
    has_pullout INTEGER NOT NULL CHECK (has_pullout IN (0, 1)),
    has_eco_aerator INTEGER NOT NULL CHECK (has_eco_aerator IN (0, 1)),
    color_final TEXT,
    metal_final TEXT,
    product_type TEXT,
    is_discounted INTEGER NOT NULL CHECK (is_discounted IN (0, 1)),
    data_quality TEXT NOT NULL
);
CREATE INDEX idx_sales_month_product ON sales(month, product_id);
CREATE INDEX idx_sales_product_month ON sales(product_id, month);
CREATE INDEX idx_products_brand ON products(brand_id);

CREATE VIEW v_sales AS
SELECT s.*, p.article_name, b.brand_name,
       CAST(SUBSTR(s.month, 1, 4) AS INTEGER) AS year,
       'Кухонные смесители' AS category,
       r.rule_id, r.subcategory, r.explanation AS classification_reason,
       CASE
           WHEN r.rule_id IS NULL THEN 1
           WHEN s.raw_filter_label IS NOT NULL
                AND s.raw_filter_label <> s.filter_label THEN 1
           ELSE 0
       END AS requires_review
FROM sales AS s
JOIN products AS p ON p.product_id = s.product_id
JOIN brands AS b ON b.brand_id = p.brand_id
LEFT JOIN classification_rules AS r
    ON r.filter_label = s.filter_label AND r.has_pullout = s.has_pullout;
