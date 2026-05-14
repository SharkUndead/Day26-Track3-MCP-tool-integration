from pathlib import Path

import pytest

from implementation.db import SQLiteAdapter, ValidationError
from implementation.init_db import create_database


@pytest.fixture()
def adapter(tmp_path: Path) -> SQLiteAdapter:
    db_path = tmp_path / "sqlite_lab_test.db"
    create_database(db_path)
    return SQLiteAdapter(db_path)


def test_search_filters_ordering_and_pagination(adapter: SQLiteAdapter):
    result = adapter.search(
        "students",
        filters={"cohort": "A1"},
        columns=["id", "name", "cohort", "gpa"],
        limit=1,
        order_by="gpa",
        descending=True,
    )

    assert result["count"] == 1
    assert result["rows"][0]["name"] == "An Nguyen"


def test_insert_returns_inserted_payload(adapter: SQLiteAdapter):
    result = adapter.insert(
        "students",
        {"name": "Lan Do", "cohort": "C3", "email": "lan.do@example.edu", "gpa": 3.55},
    )

    assert result["inserted_id"] is not None
    assert result["inserted"]["name"] == "Lan Do"
    assert result["inserted"]["cohort"] == "C3"


def test_aggregate_count_and_average(adapter: SQLiteAdapter):
    count = adapter.aggregate("students", "count")
    avg_by_cohort = adapter.aggregate("students", "avg", "gpa", group_by="cohort")

    assert count["rows"][0]["value"] == 5
    assert {row["cohort"] for row in avg_by_cohort["rows"]} == {"A1", "B2", "C3"}


@pytest.mark.parametrize(
    "call",
    [
        lambda adapter: adapter.search("missing"),
        lambda adapter: adapter.search("students", columns=["missing"]),
        lambda adapter: adapter.search("students", filters={"gpa": {"between": [3.0, 4.0]}}),
        lambda adapter: adapter.insert("students", {}),
        lambda adapter: adapter.aggregate("students", "median", "gpa"),
        lambda adapter: adapter.aggregate("students", "avg"),
    ],
)
def test_invalid_requests_are_rejected(adapter: SQLiteAdapter, call):
    with pytest.raises(ValidationError):
        call(adapter)


def test_schema_helpers(adapter: SQLiteAdapter):
    database_schema = adapter.get_database_schema()
    student_schema = adapter.get_table_schema("students")

    assert [table["table"] for table in database_schema["tables"]] == ["courses", "enrollments", "students"]
    assert any(column["name"] == "email" for column in student_schema["columns"])
