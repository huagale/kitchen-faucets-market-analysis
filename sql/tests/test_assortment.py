"""Проверки сохранности данных, неоднозначностей, фильтров и безопасного экспорта."""
import csv
import hashlib
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zipfile

SQL_DIR = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("assortment", SQL_DIR / "assortment.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AssortmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "input.csv"
        self.database = self.root / "test.sqlite"
        base = dict(
            brand_clean="Бренд Б", article_name="Модель А", month="2023-01-01",
            revenue="100", quantity="1", price="100", price_segment="Бюджетный",
            cat3="С фильтром", cat3_new="С фильтром", has_pullout="0", has_eco_aerator="0",
            color_final="черный", metal_final="", product_type="не определен",
            is_discounted="нет", data_quality="ok",
        )
        self.rows = [
            base,
            dict(base, month="2024-01-01", revenue="200", quantity="2", cat3="", cat3_new="Без фильтра", has_pullout="1"),
            dict(base, brand_clean="Бренд В", month="2024-01-01", revenue="300", quantity="3", cat3="Без фильтра", cat3_new="Без фильтра"),
            dict(base, article_name="Модель Б", month="2024-01-01", revenue="50", price="50", cat3="Без фильтра"),
            dict(base),
        ]
        self.write_source(self.rows)
        module.build_database(self.source, self.database)
        self.connection = sqlite3.connect(self.database)

    def tearDown(self):
        self.connection.close()
        self.temp.cleanup()

    def write_source(self, rows):
        with self.source.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(self.rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def records(self, query, **filters):
        headers, rows = module.query_rows(self.connection, query, module.parameters(**filters))
        return [dict(zip(headers, row)) for row in rows]

    def test_keeps_repeated_rows_and_does_not_merge_brands(self):
        result = module.validate_database(self.connection)
        self.assertEqual((result["source_rows"], result["revenue_rub"], result["units_sold"]), (5, 750, 8))
        self.assertEqual((result["product_keys"], result["unique_names"]), (3, 2))
        repeats = self.records("repeated_product_months")
        self.assertEqual(len(repeats), 1)
        self.assertEqual(repeats[0]["source_rows"], 2)

    def test_ambiguous_catalog_does_not_choose_arbitrary_subcategory(self):
        catalog = self.records("catalog_export")
        ambiguous = next(r for r in catalog if r["brand_name"] == "Бренд Б" and r["article_name"] == "Модель А")
        self.assertEqual(ambiguous["subcategory"], "Требует проверки")
        self.assertIsNone(ambiguous["rule_id"])
        self.assertEqual(ambiguous["review_status"], "needs_review")

    def test_conflicting_filter_labels_enter_review_queue(self):
        queue = self.records("classification_review")
        conflict = next(r for r in queue if r["article_name"] == "Модель Б")
        self.assertEqual(conflict["filter_conflict_rows"], 1)

    def test_year_filter_and_weighted_price(self):
        monthly = self.records("monthly_sales", year=2024)
        self.assertEqual(len(monthly), 1)
        self.assertEqual(monthly[0]["revenue_rub"], 550)
        self.assertEqual(monthly[0]["units_sold"], 6)
        self.assertEqual(monthly[0]["weighted_price_rub"], 91.67)

    def test_missing_prior_year_is_not_zero_growth(self):
        annual = self.records("brand_yoy", year=2024)
        self.assertTrue(all(r["revenue_growth_pct"] is None for r in annual))
        all_years = self.records("brand_yoy")
        brand_b = next(r for r in all_years if r["brand_name"] == "Бренд Б" and r["year"] == 2024)
        self.assertEqual(brand_b["revenue_growth_pct"], 25.0)

    def test_brand_parameter_is_bound_as_data(self):
        self.assertEqual(self.records("brand_assortment", brand="' OR 1=1 --"), [])
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM sales").fetchone()[0], 5)

    def test_invalid_build_preserves_previous_database(self):
        self.connection.close()
        before = hashlib.sha256(self.database.read_bytes()).hexdigest()
        self.write_source([dict(self.rows[0], quantity="0")])
        with self.assertRaises(ValueError):
            module.build_database(self.source, self.database)
        self.assertEqual(hashlib.sha256(self.database.read_bytes()).hexdigest(), before)
        self.connection = sqlite3.connect(self.database)

    def test_zip_source_and_empty_report(self):
        packed = self.root / "source.zip"
        with zipfile.ZipFile(packed, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(self.source, "data.csv")
        result = module.build_database(packed, self.root / "zip.sqlite")
        self.assertEqual(result["source_rows"], 5)
        audit = module.reports(self.database, self.root / "empty", module.parameters(brand="Неизвестный"))
        self.assertEqual(audit["exported_rows"]["brand_assortment"], 0)
        with (self.root / "empty/brand_assortment.csv").open(encoding="utf-8-sig") as stream:
            self.assertEqual(len(list(csv.reader(stream))), 1)

    def test_restores_prebuilt_database_without_source_csv(self):
        self.connection.close()
        packed = self.database.with_suffix('.sqlite.zip')
        with zipfile.ZipFile(packed, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(self.database, self.database.name)
        self.database.unlink()
        module.ensure_database(self.database, self.root / 'missing.csv.zip')
        self.connection = sqlite3.connect(self.database)
        self.assertEqual(module.validate_database(self.connection)['revenue_rub'], 750)


if __name__ == "__main__":
    unittest.main()
