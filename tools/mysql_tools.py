"""Read-only MySQL tools with a credential-free SQLite demonstration backend."""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Callable
from typing import Any

import pymysql
from langchain_core.tools import BaseTool, StructuredTool
from pymysql.cursors import DictCursor

from utils.config import Settings
from utils.security import SecurityError, validate_readonly_sql, validate_sql_identifier


def _database_error(code: str, message: str, *, retryable: bool = False) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {"code": code, "message": message, "retryable": retryable},
    }


class DatabaseService:
    def __init__(
        self,
        settings: Settings,
        connection_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.settings = settings
        self.connection_factory = connection_factory

    def _demo_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.executescript(
            """
            CREATE TABLE companies (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                sector TEXT NOT NULL,
                employees INTEGER NOT NULL
            );
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                company_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                annual_revenue REAL NOT NULL
            );
            CREATE TABLE sales (
                id INTEGER PRIMARY KEY,
                product_id INTEGER NOT NULL,
                region TEXT NOT NULL,
                quarter TEXT NOT NULL,
                revenue REAL NOT NULL
            );
            INSERT INTO companies VALUES
                (1, 'Northstar Labs', 'Healthcare', 420),
                (2, 'Cedar Analytics', 'Software', 180),
                (3, 'Harbor Devices', 'Manufacturing', 760);
            INSERT INTO products VALUES
                (1, 1, 'Aster', 'Diagnostics', 12500000),
                (2, 1, 'Beacon', 'Research tools', 8200000),
                (3, 2, 'Compass', 'Analytics', 9600000),
                (4, 3, 'Delta', 'Sensors', 15100000);
            INSERT INTO sales VALUES
                (1, 1, 'East', '2026-Q1', 3100000),
                (2, 1, 'West', '2026-Q1', 2950000),
                (3, 3, 'East', '2026-Q1', 2400000),
                (4, 4, 'North', '2026-Q1', 3820000);
            """
        )
        return connection

    def _real_connection(self) -> Any:
        if self.connection_factory is not None:
            return self.connection_factory()
        password = (
            self.settings.mysql_password.get_secret_value()
            if self.settings.mysql_password is not None
            else ""
        )
        return pymysql.connect(
            host=self.settings.mysql_host,
            port=self.settings.mysql_port,
            user=self.settings.mysql_user,
            password=password,
            database=self.settings.mysql_database,
            cursorclass=DictCursor,
            connect_timeout=max(1, int(self.settings.external_timeout_seconds)),
            read_timeout=max(1, int(self.settings.external_timeout_seconds)),
            write_timeout=max(1, int(self.settings.external_timeout_seconds)),
            autocommit=True,
        )

    def _list_tables_sync(self) -> dict[str, Any]:
        connection: Any = (
            self._demo_connection() if self.settings.demo_mode else self._real_connection()
        )
        try:
            if self.settings.demo_mode:
                rows = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
                tables = [str(row[0]) for row in rows]
            else:
                with connection.cursor() as cursor:
                    cursor.execute("SHOW TABLES")
                    rows = cursor.fetchall()
                tables = [str(next(iter(row.values()))) for row in rows]
            return {
                "ok": True,
                "mode": "demo" if self.settings.demo_mode else "real",
                "tables": tables,
            }
        finally:
            connection.close()

    async def list_tables(self) -> dict[str, Any]:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._list_tables_sync),
                timeout=self.settings.external_timeout_seconds + 0.1,
            )
        except TimeoutError:
            return _database_error("timeout", "database table discovery timed out", retryable=True)
        except Exception as exc:
            return _database_error(
                "provider_error",
                f"database table discovery failed: {type(exc).__name__}",
                retryable=True,
            )

    def _get_table_sync(self, table_name: str, limit: int) -> dict[str, Any]:
        table = validate_sql_identifier(table_name)
        bounded_limit = min(max(limit, 1), 100)
        connection: Any = (
            self._demo_connection() if self.settings.demo_mode else self._real_connection()
        )
        try:
            if self.settings.demo_mode:
                schema_rows = connection.execute(f"PRAGMA table_info(`{table}`)").fetchall()
                if not schema_rows:
                    return _database_error("not_found", f"table does not exist: {table}")
                columns = [
                    {"name": row[1], "type": row[2], "nullable": not bool(row[3])}
                    for row in schema_rows
                ]
                preview = connection.execute(
                    f"SELECT * FROM `{table}` LIMIT ?",  # noqa: S608 - validated identifier
                    (bounded_limit,),
                ).fetchall()
                rows = [dict(row) for row in preview]
            else:
                with connection.cursor() as cursor:
                    cursor.execute(f"DESCRIBE `{table}`")  # noqa: S608 - validated identifier
                    columns = list(cursor.fetchall())
                    cursor.execute(
                        f"SELECT * FROM `{table}` LIMIT %s",  # noqa: S608
                        (bounded_limit,),
                    )
                    rows = list(cursor.fetchall())
            return {
                "ok": True,
                "mode": "demo" if self.settings.demo_mode else "real",
                "table": table,
                "columns": columns,
                "rows": rows,
            }
        finally:
            connection.close()

    async def get_table(self, table_name: str, limit: int = 5) -> dict[str, Any]:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._get_table_sync, table_name, limit),
                timeout=self.settings.external_timeout_seconds + 0.1,
            )
        except SecurityError as exc:
            return _database_error("unsafe_identifier", str(exc))
        except TimeoutError:
            return _database_error("timeout", "database preview timed out", retryable=True)
        except Exception as exc:
            return _database_error(
                "provider_error", f"database preview failed: {type(exc).__name__}", retryable=True
            )

    def _execute_demo(self, query: str) -> list[dict[str, Any]]:
        connection = self._demo_connection()
        try:
            prefix = query.split(None, 1)[0].upper()
            if prefix == "SHOW":
                tables = self._list_tables_from_demo_connection(connection)
                return [{"table": name} for name in tables]
            if prefix in {"DESCRIBE", "DESC"}:
                parts = query.split()
                if len(parts) != 2:
                    raise SecurityError("DESCRIBE requires one table name")
                table = validate_sql_identifier(parts[1].strip("`"))
                return [dict(row) for row in connection.execute(f"PRAGMA table_info(`{table}`)")]
            translated = query
            if prefix == "EXPLAIN":
                translated = f"EXPLAIN QUERY PLAN {query[len('EXPLAIN') :].strip()}"
            cursor = connection.execute(translated)
            return [dict(row) for row in cursor.fetchmany(self.settings.max_database_rows + 1)]
        finally:
            connection.close()

    @staticmethod
    def _list_tables_from_demo_connection(connection: sqlite3.Connection) -> list[str]:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        return [str(row[0]) for row in rows]

    def _execute_real(self, query: str) -> list[dict[str, Any]]:
        connection = self._real_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(query)
                return list(cursor.fetchmany(self.settings.max_database_rows + 1))
        finally:
            connection.close()

    async def execute(self, query: str) -> dict[str, Any]:
        try:
            safe_query = validate_readonly_sql(query)
        except SecurityError as exc:
            return _database_error("unsafe_sql", str(exc))
        operation = self._execute_demo if self.settings.demo_mode else self._execute_real
        try:
            rows = await asyncio.wait_for(
                asyncio.to_thread(operation, safe_query),
                timeout=self.settings.external_timeout_seconds + 0.1,
            )
        except TimeoutError:
            return _database_error("timeout", "database query timed out", retryable=True)
        except Exception as exc:
            return _database_error(
                "query_error", f"database query failed: {type(exc).__name__}", retryable=False
            )
        truncated = len(rows) > self.settings.max_database_rows
        return {
            "ok": True,
            "mode": "demo" if self.settings.demo_mode else "real",
            "query": safe_query,
            "rows": rows[: self.settings.max_database_rows],
            "row_count": min(len(rows), self.settings.max_database_rows),
            "truncated": truncated,
        }


async def list_sql_tables(*, service: DatabaseService) -> dict[str, Any]:
    """List available SQL tables."""
    return await service.list_tables()


async def get_table_data(
    table_name: str, limit: int = 5, *, service: DatabaseService
) -> dict[str, Any]:
    """Return table schema and a small data preview."""
    return await service.get_table(table_name, limit)


async def execute_sql_query(query: str, *, service: DatabaseService) -> dict[str, Any]:
    """Execute one validated read-only SQL statement."""
    return await service.execute(query)


def make_mysql_tools(settings: Settings) -> list[BaseTool]:
    service = DatabaseService(settings)

    async def list_tables_tool() -> dict[str, Any]:
        """Discover all database tables before querying structured data."""
        return await list_sql_tables(service=service)

    async def get_table_tool(table_name: str, limit: int = 5) -> dict[str, Any]:
        """Inspect a table's schema and preview a bounded number of rows."""
        return await get_table_data(table_name, limit, service=service)

    async def query_tool(query: str) -> dict[str, Any]:
        """Run one read-only SELECT, SHOW, DESCRIBE/DESC, or EXPLAIN statement."""
        return await execute_sql_query(query, service=service)

    return [
        StructuredTool.from_function(
            coroutine=list_tables_tool,
            name="list_sql_tables",
            description="List SQL tables. Call this first for internal structured-data tasks.",
        ),
        StructuredTool.from_function(
            coroutine=get_table_tool,
            name="get_table_data",
            description="Inspect one validated table's schema and preview rows.",
        ),
        StructuredTool.from_function(
            coroutine=query_tool,
            name="execute_sql_query",
            description="Execute one Python-validated read-only SQL query and return bounded rows.",
        ),
    ]
