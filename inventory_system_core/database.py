"""SQLite connection and query helpers for the Inventory System."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


DATABASE_ERROR_TYPES = (sqlite3.DatabaseError, FileNotFoundError)
INTEGRITY_ERROR_TYPES = (sqlite3.IntegrityError,)


def _parse_sqlite_datetime(value: bytes) -> datetime:
    return datetime.fromisoformat(value.decode("utf-8"))


def _dict_row_factory(cursor: sqlite3.Cursor, row: tuple) -> dict[str, Any]:
    return {column[0]: value for column, value in zip(cursor.description, row)}


sqlite3.register_converter("DATETIME", _parse_sqlite_datetime)
sqlite3.register_converter("TIMESTAMP", _parse_sqlite_datetime)


class _ClosingSQLiteConnection(sqlite3.Connection):
    """Keep the app's connection context managers short lived."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class _DistinctGroupConcat:
    """Ordered distinct concatenation for the inventory activity tables."""

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
        separator = next(iter(self.values.values()))[1]
        ordered = sorted(self.values.items(), key=lambda pair: (str(pair[1][0]), pair[0]))
        return separator.join(value for value, _ in ordered)


class Database:
    """Open short-lived connections to the configured SQLite file."""

    def __init__(self):
        project_database = Path(__file__).resolve().parents[1] / "dunder_inventory_demo.sqlite3"
        configured_path = os.getenv("SQLITE_PATH", str(project_database)).strip()
        self.sqlite_path = Path(os.path.expanduser(configured_path)).resolve()

    def connect(self) -> sqlite3.Connection:
        if not self.sqlite_path.is_file():
            raise FileNotFoundError(
                f"SQLite database not found at {self.sqlite_path}. "
                "Set SQLITE_PATH to the existing database file."
            )
        connection = sqlite3.connect(
            self.sqlite_path,
            detect_types=sqlite3.PARSE_DECLTYPES,
            timeout=15,
            factory=_ClosingSQLiteConnection,
        )
        connection.row_factory = _dict_row_factory
        connection.execute("PRAGMA foreign_keys = ON")
        connection.create_aggregate("GROUP_CONCAT_DISTINCT", 3, _DistinctGroupConcat)
        return connection

    def fetch_one(self, sql: str, args: tuple = ()):
        connection = self.connect()
        try:
            return connection.execute(sql, args).fetchone()
        finally:
            connection.close()

    def fetch_all(self, sql: str, args: tuple = ()):
        connection = self.connect()
        try:
            return connection.execute(sql, args).fetchall()
        finally:
            connection.close()
