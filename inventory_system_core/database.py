"""Database connections for the MySQL and SQLite backends."""

from __future__ import annotations

import os
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    import pymysql
    from pymysql.cursors import DictCursor
except ImportError:  # SQLite deployments do not need PyMySQL at runtime.
    pymysql = None
    DictCursor = None


DATABASE_ERROR_TYPES = (sqlite3.DatabaseError, FileNotFoundError) + (
    (pymysql.MySQLError,) if pymysql else ()
)
INTEGRITY_ERROR_TYPES = (sqlite3.IntegrityError,) + ((pymysql.IntegrityError,) if pymysql else ())


def _parse_sqlite_datetime(value: bytes) -> datetime:
    return datetime.fromisoformat(value.decode("utf-8"))


def _dict_row_factory(cursor: sqlite3.Cursor, row: tuple) -> dict[str, Any]:
    return {column[0]: value for column, value in zip(cursor.description, row)}


sqlite3.register_converter("DATETIME", _parse_sqlite_datetime)
sqlite3.register_converter("TIMESTAMP", _parse_sqlite_datetime)


class _DistinctGroupConcat:
    """SQLite aggregate matching the small MySQL GROUP_CONCAT subset we use."""

    def __init__(self):
        self.values: dict[str, tuple[Any, str]] = {}

    def step(self, value: Any, sort_value: Any, separator: Any) -> None:
        if value is None:
            return
        text = str(value)
        self.values.setdefault(text, (sort_value, str(separator or ",")))

    def finalize(self) -> str | None:
        if not self.values:
            return None
        first = next(iter(self.values.values()))
        separator = first[1]
        values = sorted(self.values.items(), key=lambda pair: (str(pair[1][0]), pair[0]))
        return separator.join(value for value, _ in values)


class _SQLiteCursor:
    _group_concat = re.compile(
        r"GROUP_CONCAT\s*\(\s*DISTINCT\s+(.+?)\s+ORDER\s+BY\s+(.+?)"
        r"\s+SEPARATOR\s+'((?:''|[^'])*)'\s*\)",
        re.IGNORECASE | re.DOTALL,
    )

    def __init__(self, cursor: sqlite3.Cursor):
        self._cursor = cursor
        self._override_rows: list[dict[str, Any]] | None = None

    def execute(self, sql: str, args: tuple = ()):
        self._override_rows = None
        if "information_schema.COLUMNS" in sql:
            table_name = str(args[0]) if args else ""
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
                raise sqlite3.OperationalError("Invalid table name in schema check")
            self._cursor.execute(f'PRAGMA table_info("{table_name}")')
            found = any(row["name"] == "archived_at" for row in self._cursor.fetchall())
            self._override_rows = [{"n": int(found)}]
            return self

        sql = self._group_concat.sub(
            lambda match: "GROUP_CONCAT_DISTINCT(" + match.group(1) + ", "
            + match.group(2) + ", '" + match.group(3).replace("''", "'") + "')",
            sql,
        )
        sql = re.sub(r"\bFOR\s+UPDATE\b", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"%s", "?", sql)
        self._cursor.execute(sql, args or ())
        return self

    def fetchone(self):
        if self._override_rows is not None:
            return self._override_rows.pop(0) if self._override_rows else None
        return self._cursor.fetchone()

    def fetchall(self):
        if self._override_rows is not None:
            rows, self._override_rows = self._override_rows, None
            return rows
        return self._cursor.fetchall()

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def lastrowid(self) -> int | None:
        return self._cursor.lastrowid

    def close(self) -> None:
        self._cursor.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()


class _SQLiteConnection:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def cursor(self) -> _SQLiteCursor:
        return _SQLiteCursor(self._connection.cursor())

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        try:
            self.rollback() if exc_type else self.commit()
        finally:
            self.close()


class Database:
    """Open short-lived database connections based on ``DB_BACKEND``."""

    def __init__(self):
        self.backend = os.getenv("DB_BACKEND", "mysql").strip().lower()
        if self.backend not in {"mysql", "sqlite"}:
            raise RuntimeError("DB_BACKEND must be either 'mysql' or 'sqlite'.")
        self.sqlite_path = Path(os.path.expanduser(os.getenv(
            "SQLITE_PATH", "~/.inventory_system/dunder_inventory.sqlite3"
        )))

    def connect(self):
        if self.backend == "sqlite":
            if not self.sqlite_path.is_file():
                raise FileNotFoundError(
                    f"SQLite database not found at {self.sqlite_path}. "
                    "Create a copy with migrate_mysql_to_sqlite.py before starting the app."
                )
            connection = sqlite3.connect(
                self.sqlite_path,
                detect_types=sqlite3.PARSE_DECLTYPES,
                timeout=15,
            )
            connection.row_factory = _dict_row_factory
            connection.execute("PRAGMA foreign_keys = ON")
            connection.create_aggregate("GROUP_CONCAT_DISTINCT", 3, _DistinctGroupConcat)
            connection.create_function("CONCAT", -1, self._concat)
            connection.create_function("DATE_FORMAT", 2, self._date_format)
            connection.create_function("NOW", 0, self._now)
            return _SQLiteConnection(connection)

        if pymysql is None:
            raise RuntimeError("PyMySQL is required when DB_BACKEND=mysql.")
        return pymysql.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASS", ""),
            database=os.getenv("DB_NAME", "dunder_inventory"),
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
        )

    @staticmethod
    def _concat(*values: Any) -> str | None:
        if any(value is None for value in values):
            return None
        return "".join(str(value) for value in values)

    @staticmethod
    def _date_format(value: Any, format_string: str) -> str | None:
        if value is None:
            return None
        value_text = value.isoformat(sep=" ") if isinstance(value, datetime) else str(value)
        try:
            parsed = datetime.fromisoformat(value_text)
        except ValueError:
            try:
                parsed = datetime.combine(date.fromisoformat(value_text), datetime.min.time())
            except ValueError:
                return None
        return parsed.strftime(str(format_string).replace("%%", "%"))

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def fetch_one(self, sql: str, args: tuple = ()):
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute(sql, args)
            return cursor.fetchone()

    def fetch_all(self, sql: str, args: tuple = ()):
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute(sql, args)
            return cursor.fetchall()
