from __future__ import annotations

import json
import tempfile
from pathlib import Path

try:
    from .db import SQLiteAdapter, ValidationError
    from .init_db import create_database
except ImportError:
    from db import SQLiteAdapter, ValidationError
    from init_db import create_database


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "sqlite_lab_verify.db"
        create_database(db_path)
        adapter = SQLiteAdapter(db_path)

        tables = adapter.list_tables()
        assert_true(tables == ["courses", "enrollments", "students"], f"Unexpected tables: {tables}")

        schema = adapter.get_database_schema()
        assert_true(len(schema["tables"]) == 3, "Full schema resource data is incomplete")

        student_schema = adapter.get_table_schema("students")
        assert_true(any(col["name"] == "cohort" for col in student_schema["columns"]), "students schema missing cohort")

        search_result = adapter.search(
            "students",
            filters={"cohort": "A1"},
            columns=["id", "name", "cohort", "gpa"],
            order_by="gpa",
            descending=True,
        )
        assert_true(search_result["count"] == 2, "Search should return two A1 students")

        inserted = adapter.insert(
            "students",
            {"name": "Test Student", "cohort": "A1", "email": "test.student@example.edu", "gpa": 3.33},
        )
        assert_true(inserted["inserted"]["id"] is not None, "Insert should return inserted row")

        aggregate = adapter.aggregate("students", "avg", "gpa", group_by="cohort")
        assert_true(any(row["cohort"] == "A1" for row in aggregate["rows"]), "Aggregate should group by cohort")

        invalid_cases = [
            lambda: adapter.search("missing_table"),
            lambda: adapter.search("students", filters={"cohort": {"contains": "A1"}}),
            lambda: adapter.insert("students", {}),
            lambda: adapter.aggregate("students", "median", "gpa"),
            lambda: adapter.aggregate("students", "avg"),
        ]
        for invalid in invalid_cases:
            try:
                invalid()
            except ValidationError:
                continue
            raise AssertionError("Invalid request did not raise ValidationError")

        print(
            json.dumps(
                {
                    "ok": True,
                    "checks": [
                        "database initialized",
                        "schema readable",
                        "table schema readable",
                        "search works",
                        "insert works",
                        "aggregate works",
                        "invalid requests rejected",
                    ],
                    "database": str(db_path),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
