from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


class ValidationError(ValueError):
    """Raised when a request cannot be safely executed."""


class SQLiteAdapter:
    ALLOWED_OPERATORS = {
        "eq": "=",
        "ne": "!=",
        "gt": ">",
        "gte": ">=",
        "lt": "<",
        "lte": "<=",
        "like": "LIKE",
        "in": "IN",
    }
    ALLOWED_METRICS = {"count", "avg", "sum", "min", "max"}
    IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def list_tables(self) -> list[str]:
        with closing(self.connect()) as conn:
            rows = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        return [row["name"] for row in rows]

    def get_table_schema(self, table: str) -> dict[str, Any]:
        self._validate_table(table)
        with closing(self.connect()) as conn:
            columns = conn.execute(f"PRAGMA table_info({self._quote_identifier(table)})").fetchall()
            foreign_keys = conn.execute(f"PRAGMA foreign_key_list({self._quote_identifier(table)})").fetchall()

        return {
            "table": table,
            "columns": [
                {
                    "name": row["name"],
                    "type": row["type"],
                    "not_null": bool(row["notnull"]),
                    "default": row["dflt_value"],
                    "primary_key": bool(row["pk"]),
                }
                for row in columns
            ],
            "foreign_keys": [
                {
                    "column": row["from"],
                    "references_table": row["table"],
                    "references_column": row["to"],
                }
                for row in foreign_keys
            ],
        }

    def get_database_schema(self) -> dict[str, Any]:
        return {"tables": [self.get_table_schema(table) for table in self.list_tables()]}

    def search(
        self,
        table: str,
        columns: list[str] | None = None,
        filters: dict[str, Any] | list[dict[str, Any]] | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict[str, Any]:
        table_columns = self._validate_table(table)
        selected = self._validate_columns(columns, table_columns) if columns else table_columns
        limit, offset = self._validate_pagination(limit, offset)

        where_sql, params = self._build_where(table_columns, filters)
        order_sql = ""
        if order_by:
            self._validate_column(order_by, table_columns)
            direction = "DESC" if descending else "ASC"
            order_sql = f" ORDER BY {self._quote_identifier(order_by)} {direction}"

        sql = (
            f"SELECT {', '.join(self._quote_identifier(column) for column in selected)} "
            f"FROM {self._quote_identifier(table)}{where_sql}{order_sql} LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])

        with closing(self.connect()) as conn:
            rows = [dict(row) for row in conn.execute(sql, params).fetchall()]

        return {
            "table": table,
            "columns": selected,
            "limit": limit,
            "offset": offset,
            "count": len(rows),
            "rows": rows,
        }

    def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        table_columns = self._validate_table(table)
        if not values:
            raise ValidationError("Insert values cannot be empty")
        if not isinstance(values, dict):
            raise ValidationError("Insert values must be an object")

        columns = list(values.keys())
        self._validate_columns(columns, table_columns)
        placeholders = ", ".join("?" for _ in columns)
        column_sql = ", ".join(self._quote_identifier(column) for column in columns)
        sql = f"INSERT INTO {self._quote_identifier(table)} ({column_sql}) VALUES ({placeholders})"

        with closing(self.connect()) as conn:
            cursor = conn.execute(sql, [values[column] for column in columns])
            conn.commit()
            row_id = cursor.lastrowid
            row = conn.execute(
                f"SELECT * FROM {self._quote_identifier(table)} WHERE rowid = ?",
                [row_id],
            ).fetchone()

        return {
            "table": table,
            "inserted_id": row_id,
            "inserted": dict(row) if row else {**values, "id": row_id},
        }

    def aggregate(
        self,
        table: str,
        metric: str,
        column: str | None = None,
        filters: dict[str, Any] | list[dict[str, Any]] | None = None,
        group_by: str | list[str] | None = None,
    ) -> dict[str, Any]:
        table_columns = self._validate_table(table)
        metric = metric.lower()
        if metric not in self.ALLOWED_METRICS:
            raise ValidationError(f"Unsupported aggregate metric: {metric}")

        if metric == "count" and column is None:
            metric_expr = "COUNT(*)"
        else:
            if column is None:
                raise ValidationError(f"Aggregate metric '{metric}' requires a column")
            self._validate_column(column, table_columns)
            metric_expr = f"{metric.upper()}({self._quote_identifier(column)})"

        group_columns = self._normalize_group_by(group_by)
        self._validate_columns(group_columns, table_columns)
        select_parts = [self._quote_identifier(column) for column in group_columns]
        select_parts.append(f"{metric_expr} AS value")
        where_sql, params = self._build_where(table_columns, filters)
        group_sql = ""
        if group_columns:
            group_sql = " GROUP BY " + ", ".join(self._quote_identifier(column) for column in group_columns)

        sql = f"SELECT {', '.join(select_parts)} FROM {self._quote_identifier(table)}{where_sql}{group_sql}"
        with closing(self.connect()) as conn:
            rows = [dict(row) for row in conn.execute(sql, params).fetchall()]

        return {
            "table": table,
            "metric": metric,
            "column": column,
            "group_by": group_columns,
            "rows": rows,
        }

    def _validate_table(self, table: str) -> list[str]:
        self._validate_identifier(table, "table")
        tables = self.list_tables()
        if table not in tables:
            raise ValidationError(f"Unknown table: {table}. Known tables: {', '.join(tables)}")
        schema = self.get_table_columns(table)
        return schema

    def get_table_columns(self, table: str) -> list[str]:
        self._validate_identifier(table, "table")
        with closing(self.connect()) as conn:
            rows = conn.execute(f"PRAGMA table_info({self._quote_identifier(table)})").fetchall()
        return [row["name"] for row in rows]

    def _validate_columns(self, columns: list[str], known_columns: list[str]) -> list[str]:
        for column in columns:
            self._validate_column(column, known_columns)
        return columns

    def _validate_column(self, column: str, known_columns: list[str]) -> None:
        self._validate_identifier(column, "column")
        if column not in known_columns:
            raise ValidationError(f"Unknown column: {column}. Known columns: {', '.join(known_columns)}")

    def _validate_identifier(self, identifier: str, kind: str) -> None:
        if not isinstance(identifier, str) or not self.IDENTIFIER_RE.match(identifier):
            raise ValidationError(f"Invalid {kind} identifier: {identifier!r}")

    def _validate_pagination(self, limit: int, offset: int) -> tuple[int, int]:
        try:
            limit = int(limit)
            offset = int(offset)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Limit and offset must be integers") from exc
        if limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100")
        if offset < 0:
            raise ValidationError("Offset must be greater than or equal to 0")
        return limit, offset

    def _build_where(
        self,
        known_columns: list[str],
        filters: dict[str, Any] | list[dict[str, Any]] | None,
    ) -> tuple[str, list[Any]]:
        normalized = self._normalize_filters(filters)
        if not normalized:
            return "", []

        clauses: list[str] = []
        params: list[Any] = []
        for item in normalized:
            column = item["column"]
            operator = item["operator"]
            value = item["value"]
            self._validate_column(column, known_columns)
            if operator not in self.ALLOWED_OPERATORS:
                raise ValidationError(f"Unsupported filter operator: {operator}")

            if operator == "in":
                if not isinstance(value, list) or not value:
                    raise ValidationError("'in' filter requires a non-empty list value")
                placeholders = ", ".join("?" for _ in value)
                clauses.append(f"{self._quote_identifier(column)} IN ({placeholders})")
                params.extend(value)
            else:
                clauses.append(f"{self._quote_identifier(column)} {self.ALLOWED_OPERATORS[operator]} ?")
                params.append(value)

        return " WHERE " + " AND ".join(clauses), params

    def _normalize_filters(self, filters: dict[str, Any] | list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        if filters is None:
            return []
        if isinstance(filters, list):
            items = filters
        elif isinstance(filters, dict):
            items = []
            for column, spec in filters.items():
                if isinstance(spec, dict):
                    if len(spec) != 1:
                        raise ValidationError(f"Filter for column '{column}' must contain exactly one operator")
                    operator, value = next(iter(spec.items()))
                else:
                    operator, value = "eq", spec
                items.append({"column": column, "operator": operator, "value": value})
        else:
            raise ValidationError("Filters must be an object or a list")

        normalized = []
        for item in items:
            if not isinstance(item, dict):
                raise ValidationError("Each filter must be an object")
            try:
                column = item["column"]
                operator = item.get("operator", "eq")
                value = item["value"]
            except KeyError as exc:
                raise ValidationError("Filter objects require column and value fields") from exc
            normalized.append({"column": column, "operator": str(operator).lower(), "value": value})
        return normalized

    def _normalize_group_by(self, group_by: str | list[str] | None) -> list[str]:
        if group_by is None:
            return []
        if isinstance(group_by, str):
            return [group_by]
        if isinstance(group_by, list) and all(isinstance(item, str) for item in group_by):
            return group_by
        raise ValidationError("group_by must be a string or list of strings")

    def _quote_identifier(self, identifier: str) -> str:
        self._validate_identifier(identifier, "identifier")
        return f'"{identifier}"'
