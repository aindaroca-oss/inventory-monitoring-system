"""Copy MySQL records into a new SQLite file without writing to MySQL.

Run locally with the existing dunder_inventory MySQL service available. The
source connection is used only for SELECTs. The output file must not exist.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pymysql
from pymysql.cursors import DictCursor


TABLES = (
    "supplier",
    "shelf",
    "office_personnel",
    "inventory_admin",
    "users",
    "item",
    "supply_request",
    "transaction_log",
    "low_stock_alert",
)


def sqlite_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytearray, memoryview)):
        return bytes(value)
    return value


def migrate(output: Path) -> None:
    output = output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing file: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    source = pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASS", ""),
        database=os.getenv("DB_NAME", "dunder_inventory"),
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
        read_timeout=30,
        write_timeout=30,
    )
    target = None
    created_output = False
    counts: dict[str, int] = {}
    try:
        target = sqlite3.connect(output, detect_types=sqlite3.PARSE_DECLTYPES)
        created_output = True
        target.execute("PRAGMA foreign_keys = ON")
        schema = Path(__file__).with_name("schema.sqlite.sql").read_text(encoding="utf-8")
        target.executescript(schema)
        target.execute("BEGIN")

        with source.cursor() as source_cursor:
            for table in TABLES:
                source_cursor.execute(f"SELECT * FROM `{table}`")
                source_columns = [column[0] for column in source_cursor.description]
                source_rows = source_cursor.fetchall()
                target_columns = {
                    row[1] for row in target.execute(f'PRAGMA table_info("{table}")').fetchall()
                }
                unmapped_columns = [
                    column for column in source_columns if column not in target_columns
                ]
                if unmapped_columns:
                    raise RuntimeError(
                        f"Cannot safely copy {table}: SQLite schema has no matching "
                        f"column(s): {', '.join(unmapped_columns)}. Update schema.sqlite.sql "
                        "before migrating so no MySQL data is silently omitted."
                    )
                if source_rows:
                    columns = source_columns
                    quoted_columns = ", ".join(f'"{column}"' for column in columns)
                    placeholders = ", ".join("?" for _ in columns)
                    values = [
                        tuple(sqlite_value(row[column]) for column in columns)
                        for row in source_rows
                    ]
                    target.executemany(
                        f'INSERT INTO "{table}" ({quoted_columns}) VALUES ({placeholders})',
                        values,
                    )
                counts[table] = len(source_rows)

        violations = target.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"SQLite foreign-key check failed: {violations[:5]}")
        target.commit()
    except Exception:
        if target is not None:
            target.rollback()
        if created_output and output.exists():
            output.unlink()
        raise
    finally:
        if target is not None:
            target.close()
        source.close()

    print(f"Created SQLite copy: {output}")
    for table, count in counts.items():
        print(f"{table}: {count} rows")
    print("Source MySQL database was read only and was not changed.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dunder_inventory_demo.sqlite3"),
        help="new SQLite file to create (existing files are never overwritten)",
    )
    args = parser.parse_args()
    migrate(args.output)


if __name__ == "__main__":
    main()
