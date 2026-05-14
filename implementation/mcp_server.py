from __future__ import annotations

import json
from functools import wraps
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

try:
    from .db import SQLiteAdapter, ValidationError
    from .init_db import DEFAULT_DB_PATH, create_database
except ImportError:
    from db import SQLiteAdapter, ValidationError
    from init_db import DEFAULT_DB_PATH, create_database


if not Path(DEFAULT_DB_PATH).exists():
    create_database(DEFAULT_DB_PATH)

adapter = SQLiteAdapter(DEFAULT_DB_PATH)
mcp = FastMCP("SQLite Lab MCP Server")


def _handle_validation(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    return wrapper


@mcp.tool(name="search")
@_handle_validation
def search(
    table: str,
    filters: dict[str, Any] | list[dict[str, Any]] | None = None,
    columns: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str | None = None,
    descending: bool = False,
) -> dict[str, Any]:
    """Search rows in a database table with optional filters, ordering, and pagination."""
    return {"ok": True, **adapter.search(table, columns, filters, limit, offset, order_by, descending)}


@mcp.tool(name="insert")
@_handle_validation
def insert(table: str, values: dict[str, Any]) -> dict[str, Any]:
    """Insert one row into a database table after validating table and column names."""
    return {"ok": True, **adapter.insert(table, values)}


@mcp.tool(name="aggregate")
@_handle_validation
def aggregate(
    table: str,
    metric: str,
    column: str | None = None,
    filters: dict[str, Any] | list[dict[str, Any]] | None = None,
    group_by: str | list[str] | None = None,
) -> dict[str, Any]:
    """Run count, avg, sum, min, or max aggregates with optional filters and grouping."""
    return {"ok": True, **adapter.aggregate(table, metric, column, filters, group_by)}


@mcp.resource("schema://database")
def database_schema() -> str:
    """Return the full SQLite database schema as JSON text."""
    return json.dumps(adapter.get_database_schema(), indent=2)


@mcp.resource("schema://table/{table_name}")
def table_schema(table_name: str) -> str:
    """Return one table schema as JSON text."""
    try:
        payload = adapter.get_table_schema(table_name)
    except ValidationError as exc:
        payload = {"ok": False, "error": str(exc)}
    return json.dumps(payload, indent=2)


if __name__ == "__main__":
    mcp.run()
