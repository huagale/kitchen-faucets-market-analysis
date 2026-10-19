#!/usr/bin/env python3
"""SQL-анализ исходного проекта. Python 3.10+, только стандартная библиотека.

Из корня: python sql/assortment.py
Выгрузка: python sql/assortment.py export --query brand_assortment --year 2024
"""
from __future__ import annotations

import argparse
from contextlib import closing, contextmanager
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import zipfile

SQL_DIR = Path(__file__).resolve().parent
ROOT = SQL_DIR.parent
DEFAULT_SOURCE = ROOT / "data/processed/faucets_sales_cleaned.csv.zip"
DEFAULT_DB = ROOT / "data/sql/faucets.sqlite"
DEFAULT_REPORTS = ROOT / "reports/sql"
QUERIES = {
    p.stem.split("_", 1)[1]: p
    for p in sorted((SQL_DIR / "queries").glob("*.sql"))
}
SCHEMA_VERSION = "1"
REQUIRED_FIELDS = {
    "brand_clean", "article_name", "month", "revenue", "quantity", "price",
    "price_segment", "cat3", "cat3_new", "has_pullout", "has_eco_aerator",
    "color_final", "metal_final", "product_type", "is_discounted", "data_quality",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@contextmanager
def source_reader(path: Path):
    """Читает CSV либо ZIP ровно с одним CSV; извлечение файла не требуется."""
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            members = [n for n in archive.namelist() if n.lower().endswith(".csv") and not n.endswith("/")]
            if len(members) != 1:
                raise ValueError("В ZIP должен находиться ровно один CSV.")
            with archive.open(members[0]) as binary:
                with io.TextIOWrapper(binary, encoding="utf-8-sig", newline="") as text:
                    yield csv.DictReader(text)
    else:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            yield csv.DictReader(stream)


def integer(value: str, field: str, record: int) -> int:
    try:
        number = Decimal(value)
        if not number.is_finite() or number != number.to_integral_value():
            raise ValueError
        return int(number)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"Запись {record}: {field} должно быть целым числом, получено {value!r}.") from None


def flag(value: str, field: str, record: int) -> int:
    result = integer(value, field, record)
    if result not in (0, 1):
        raise ValueError(f"Запись {record}: {field} должно быть 0 или 1.")
    return result


def optional(value: str | None) -> str | None:
    return None if value is None or not value.strip() else value


def validate_database(connection: sqlite3.Connection) -> dict:
    """Проверяет сохранность строк, сумм, годов и кардинальность JOIN."""
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
    metadata = dict(connection.execute("SELECT key, value FROM metadata"))
    if metadata.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Версия схемы не соответствует скрипту; выполните build.")
    source_stats = json.loads(metadata["source_stats"])
    rows, revenue, quantity = connection.execute(
        "SELECT COUNT(*), COALESCE(SUM(revenue),0), COALESCE(SUM(quantity),0) FROM sales"
    ).fetchone()
    joined_rows = connection.execute("SELECT COUNT(*) FROM v_sales").fetchone()[0]
    years = {
        str(y): {"rows": n, "revenue_rub": r, "units": q}
        for y, n, r, q in connection.execute(
            "SELECT year, COUNT(*), SUM(revenue), SUM(quantity) FROM v_sales GROUP BY year"
        )
    }
    checks = {
        "integrity_ok": integrity == "ok",
        "foreign_keys_ok": not foreign_errors,
        "source_rows_preserved": rows == source_stats["rows"],
        "source_revenue_preserved": revenue == source_stats["revenue_rub"],
        "source_units_preserved": quantity == source_stats["units"],
        "join_does_not_duplicate_or_lose_rows": joined_rows == rows,
        "annual_totals_preserved": years == source_stats["years"],
    }
    if not all(checks.values()):
        raise ValueError(
            "Не пройдены проверки: " + ", ".join(k for k, v in checks.items() if not v)
            + f"; SQL: rows={rows}, revenue={revenue}, units={quantity}; "
            + f"CSV: rows={source_stats['rows']}, revenue={source_stats['revenue_rub']}, units={source_stats['units']}"
        )
    return {
        "checks": checks,
        "source_file": metadata["source_file"],
        "source_sha256": metadata["source_sha256"],
        "rules_sha256": metadata["rules_sha256"],
        "source_rows": rows, "revenue_rub": revenue, "units_sold": quantity,
        "years": years,
        "brands": connection.execute("SELECT COUNT(*) FROM brands").fetchone()[0],
        "product_keys": connection.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "unique_names": connection.execute("SELECT COUNT(DISTINCT article_name) FROM products").fetchone()[0],
        "unmatched_rule_rows": connection.execute("SELECT COUNT(*) FROM v_sales WHERE rule_id IS NULL").fetchone()[0],
        "repeated_product_month_groups": connection.execute(
            "SELECT COUNT(*) FROM (SELECT product_id,month FROM sales GROUP BY product_id,month HAVING COUNT(*)>1)"
        ).fetchone()[0],
    }


def build_database(source: Path = DEFAULT_SOURCE, database: Path = DEFAULT_DB) -> dict:
    source, database = Path(source), Path(database)
    if not source.is_file():
        raise FileNotFoundError(f"Не найден очищенный набор: {source}")
    database.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=database.parent, suffix=".sqlite.tmp", delete=False) as temp:
        temporary = Path(temp.name)
    connection = None
    try:
        connection = sqlite3.connect(temporary)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript((SQL_DIR / "schema.sql").read_text(encoding="utf-8"))
        rules_file = SQL_DIR / "classification_rules.csv"
        with rules_file.open(encoding="utf-8-sig", newline="") as stream:
            rules = list(csv.DictReader(stream))
        connection.executemany(
            "INSERT INTO classification_rules VALUES (:rule_id,:filter_label,:has_pullout,:subcategory,:explanation)",
            rules,
        )
        brands: dict[str, int] = {}
        products: dict[tuple[str, str], int] = {}
        stats = {"rows": 0, "revenue_rub": 0, "units": 0, "years": {}}
        batch = []
        with source_reader(source) as reader:
            missing = REQUIRED_FIELDS - set(reader.fieldnames or [])
            if missing:
                raise ValueError("Нет обязательных колонок: " + ", ".join(sorted(missing)))
            for record_id, row in enumerate(reader, start=1):
                brand, name = row["brand_clean"], row["article_name"]
                if not brand.strip() or not name.strip():
                    raise ValueError(f"Запись {record_id}: пустой бренд или наименование.")
                if brand not in brands:
                    brands[brand] = len(brands) + 1
                    connection.execute("INSERT INTO brands VALUES (?,?)", (brands[brand], brand))
                key = (brand, name)
                if key not in products:
                    products[key] = len(products) + 1
                    connection.execute("INSERT INTO products VALUES (?,?,?)", (products[key], brands[brand], name))
                month = date.fromisoformat(row["month"])
                if month.day != 1:
                    raise ValueError(f"Запись {record_id}: ожидается первый день месяца.")
                revenue = integer(row["revenue"], "revenue", record_id)
                quantity = integer(row["quantity"], "quantity", record_id)
                price = float(row["price"])
                if revenue < 0 or quantity <= 0 or not math.isfinite(price) or price < 0:
                    raise ValueError(f"Запись {record_id}: недопустимая выручка, количество или цена.")
                if row["data_quality"] != "ok":
                    raise ValueError(f"Запись {record_id}: SQL-модуль ожидает очищенные строки data_quality=ok.")
                if row["is_discounted"] not in ("да", "нет"):
                    raise ValueError(f"Запись {record_id}: неизвестное значение is_discounted.")
                batch.append((
                    record_id, products[key], month.isoformat(), revenue, quantity, price,
                    row["price_segment"], optional(row["cat3"]), optional(row["cat3_new"]),
                    flag(row["has_pullout"], "has_pullout", record_id),
                    flag(row["has_eco_aerator"], "has_eco_aerator", record_id),
                    optional(row["color_final"]), optional(row["metal_final"]),
                    optional(row["product_type"]), int(row["is_discounted"] == "да"), row["data_quality"],
                ))
                stats["rows"] += 1
                stats["revenue_rub"] += revenue
                stats["units"] += quantity
                annual = stats["years"].setdefault(str(month.year), {"rows": 0, "revenue_rub": 0, "units": 0})
                annual["rows"] += 1
                annual["revenue_rub"] += revenue
                annual["units"] += quantity
                if len(batch) >= 2000:
                    connection.executemany("INSERT INTO sales VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch)
                    batch.clear()
        if not stats["rows"]:
            raise ValueError("Исходный набор пуст; существующая база сохранена.")
        if batch:
            connection.executemany("INSERT INTO sales VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch)
        metadata = {
            "schema_version": SCHEMA_VERSION, "source_file": source.name,
            "source_sha256": sha256(source), "rules_sha256": sha256(rules_file),
            "source_stats": json.dumps(stats, ensure_ascii=False, sort_keys=True),
        }
        connection.executemany("INSERT INTO metadata VALUES (?,?)", metadata.items())
        connection.commit()
        result = validate_database(connection)
        connection.execute("ANALYZE")
        connection.commit()
        connection.close()
        connection = None
        temporary.replace(database)
        return result
    finally:
        if connection is not None:
            connection.close()
        temporary.unlink(missing_ok=True)


def ensure_database(database: Path, source: Path) -> None:
    """Использует готовую базу, восстанавливает ZIP или собирает из CSV."""
    if not database.exists():
        packed = database.with_suffix(database.suffix + ".zip")
        if packed.is_file():
            database.parent.mkdir(parents=True, exist_ok=True)
            temporary = database.with_suffix(".restore.tmp")
            try:
                with zipfile.ZipFile(packed) as archive:
                    if archive.namelist() != [database.name]:
                        raise ValueError("Неверное содержимое архива базы.")
                    with archive.open(database.name) as incoming, temporary.open("wb") as outgoing:
                        shutil.copyfileobj(incoming, outgoing)
                with closing(sqlite3.connect(temporary)) as connection:
                    validate_database(connection)
                temporary.replace(database)
            finally:
                temporary.unlink(missing_ok=True)
        else:
            build_database(source, database)
    with closing(sqlite3.connect(database)) as connection:
        metadata = dict(connection.execute("SELECT key,value FROM metadata"))
    if metadata.get("rules_sha256") != sha256(SQL_DIR / "classification_rules.csv"):
        build_database(source, database)
    elif source.is_file() and metadata.get("source_sha256") != sha256(source):
        build_database(source, database)


def parameters(year: int | None = None, brand: str | None = None, limit: int = 1000) -> dict:
    if year is not None and not 1 <= year <= 9999:
        raise ValueError("Год должен быть от 1 до 9999.")
    if limit == 0 or limit < -1:
        raise ValueError("Лимит должен быть положительным либо -1 для всех строк.")
    return {
        "date_from": f"{year:04d}-01-01" if year else "0001-01-01",
        "date_to": f"{year:04d}-12-31" if year else "9999-12-31",
        "brand": brand, "limit": limit,
    }


def query_rows(connection: sqlite3.Connection, query: str, params: dict) -> tuple[list[str], list[tuple]]:
    if query not in QUERIES:
        raise ValueError("Неизвестный запрос: " + query)
    cursor = connection.execute(QUERIES[query].read_text(encoding="utf-8"), params)
    return [d[0] for d in cursor.description], cursor.fetchall()


def write_csv(path: Path, headers: list[str], rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)


def markdown_table(headers, rows) -> str:
    def cell(value):
        return "—" if value is None else str(value).replace("|", "\\|").replace("\n", " ")
    return "\n".join([
        "| " + " | ".join(map(cell, headers)) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *["| " + " | ".join(map(cell, row)) + " |" for row in rows],
    ])


def reports(database: Path = DEFAULT_DB, output: Path = DEFAULT_REPORTS, params: dict | None = None) -> dict:
    params = parameters() if params is None else params
    output.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        validation = validate_database(connection)
        results = {}
        counts = {}
        for name in QUERIES:
            headers, rows = query_rows(connection, name, params)
            write_csv(output / f"{name}.csv", headers, rows)
            results[name] = (headers, rows)
            counts[name] = len(rows)
    audit = {"database_validation": validation, "report_filters": params, "exported_rows": counts}
    (output / "validation.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    monthly = results["monthly_sales"][1]
    year_rows = {}
    for month, _, _, _, revenue, quantity, _ in monthly:
        annual = year_rows.setdefault(month[:4], [0, 0])
        annual[0] += revenue
        annual[1] += quantity
    yearly = [(y, f"{r:,}".replace(",", " "), f"{q:,}".replace(",", " ")) for y, (r, q) in sorted(year_rows.items())]
    content = [
        "# SQL: готовые результаты анализа ассортимента", "",
        "Результаты получены из исходного очищенного CSV проекта; синтетические продажи не добавлялись.", "",
        "Фильтры выгрузок: `" + json.dumps(params, ensure_ascii=False) + "`.", "",
        "## Объём продаж", "", markdown_table(["Год", "Выручка, руб.", "Продано, шт."], yearly), "",
        "## Проверка загрузки", "",
        f"Полная база: **{validation['source_rows']:,}** наблюдений, **{validation['brands']:,}** брендов/групп, "
        f"**{validation['product_keys']:,}** сочетаний бренд+наименование, **{validation['unique_names']:,}** уникальных наименований.", "",
        "Все семь проверок сохранности строк, денежных сумм, количества, годовых итогов, связей и целостности пройдены. "
        "Это проверка переноса данных в SQL, а не оценка точности исходного парсинга.", "",
        "## Первые 10 брендов в выбранном срезе", "",
        markdown_table(results["brand_assortment"][0], results["brand_assortment"][1][:10]), "",
        "## Товарные группы по исходным признакам", "",
        markdown_table(*results["subcategory_assortment"]), "",
        "Группы определяются правилами из [classification_rules.csv](../../sql/classification_rules.csv). "
        "Отсутствие отметки функции в данных не означает её фактическое отсутствие у товара. "
        "Это учебные аналитические группы внутри одной категории кухонных смесителей.", "",
        "## Полнота и согласованность данных", "", markdown_table(*results["quality_checks"]), "",
        "## Готовые CSV", "",
        markdown_table(["Запрос", "Строк в выгрузке"], [(f"[{n}.csv]({n}.csv)", c) for n, c in counts.items()]), "",
        "Каталог, очередь проверки и повторяющиеся товаро-месяцы ограничены параметром `limit`; это демонстрационные выгрузки. "
        "`--limit -1` выгружает их полностью. Остальные CSV содержат все строки соответствующего отчёта.", "",
        "Количество сочетаний бренд+наименование может пересекаться между сегментами и группами. "
        "Исходные повторяющиеся товаро-месяцы сохранены: отдельного артикула нет, поэтому они не удаляются автоматически.", "",
        "[Описание модели, запросов и запуска](../../sql/README.md). [Машиночитаемая проверка](validation.json).", "",
    ]
    (output / "README.md").write_text("\n".join(content), encoding="utf-8")
    return audit


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", default="run", choices=["run", "build", "reports", "export", "validate", "list"])
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORTS)
    parser.add_argument("--query", choices=sorted(QUERIES), default="brand_assortment")
    parser.add_argument("--year", type=int)
    parser.add_argument("--brand", help="Точное нормализованное имя бренда, например Shimizu")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        params = parameters(args.year, args.brand, args.limit)
        if args.action == "list":
            print("\n".join(QUERIES))
            return 0
        if args.action in ("run", "build"):
            validation = build_database(args.source, args.db)
            print(f"База готова: {validation['source_rows']:,} строк; выручка {validation['revenue_rub']:,} руб.")
        else:
            ensure_database(args.db, args.source)
        if args.action in ("run", "reports"):
            audit = reports(args.db, args.output_dir, params)
            print(f"Готово {len(audit['exported_rows'])} CSV-отчётов: {args.output_dir}")
        elif args.action == "export":
            with closing(sqlite3.connect(args.db.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
                headers, rows = query_rows(connection, args.query, params)
            out = args.out or args.output_dir / f"{args.query}_filtered.csv"
            write_csv(out, headers, rows)
            print(f"Выгружено {len(rows)} строк: {out}")
        elif args.action == "validate":
            with closing(sqlite3.connect(args.db)) as connection:
                print(json.dumps(validate_database(connection), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, sqlite3.Error, zipfile.BadZipFile) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
