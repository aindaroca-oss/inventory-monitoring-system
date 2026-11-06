"""MySQL connection and query helpers."""

import os

import pymysql
from pymysql.cursors import DictCursor


class Database:
    """Opens short-lived MySQL connections from local environment settings."""

    def connect(self):
        return pymysql.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASS", ""),
            database=os.getenv("DB_NAME", "inventory_system"),
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
        )

    def fetch_one(self, sql: str, args: tuple = ()):
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute(sql, args)
            return cursor.fetchone()

    def fetch_all(self, sql: str, args: tuple = ()):
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute(sql, args)
            return cursor.fetchall()
