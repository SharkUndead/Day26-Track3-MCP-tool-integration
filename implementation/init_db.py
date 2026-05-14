from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


DEFAULT_DB_PATH = Path(__file__).with_name("sqlite_lab.db")


SCHEMA_SQL = """
DROP TABLE IF EXISTS enrollments;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS students;

CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cohort TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    gpa REAL NOT NULL CHECK (gpa >= 0 AND gpa <= 4),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    credits INTEGER NOT NULL CHECK (credits > 0)
);

CREATE TABLE enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    score REAL NOT NULL CHECK (score >= 0 AND score <= 100),
    semester TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (course_id) REFERENCES courses(id),
    UNIQUE (student_id, course_id, semester)
);
"""


SEED_SQL = """
INSERT INTO students (name, cohort, email, gpa) VALUES
    ('An Nguyen', 'A1', 'an.nguyen@example.edu', 3.70),
    ('Binh Tran', 'A1', 'binh.tran@example.edu', 3.45),
    ('Chi Le', 'B2', 'chi.le@example.edu', 3.90),
    ('Dung Pham', 'B2', 'dung.pham@example.edu', 3.20),
    ('Minh Hoang', 'C3', 'minh.hoang@example.edu', 3.60);

INSERT INTO courses (code, title, credits) VALUES
    ('MCP101', 'Model Context Protocol Basics', 3),
    ('DB201', 'Applied Databases', 4),
    ('AI310', 'AI Tool Integration', 3);

INSERT INTO enrollments (student_id, course_id, score, semester) VALUES
    (1, 1, 91.5, '2026A'),
    (1, 2, 87.0, '2026A'),
    (2, 1, 82.0, '2026A'),
    (2, 3, 88.5, '2026A'),
    (3, 1, 96.0, '2026A'),
    (3, 2, 93.0, '2026A'),
    (4, 2, 78.5, '2026A'),
    (5, 3, 90.0, '2026A');
"""


def create_database(db_path: str | Path = DEFAULT_DB_PATH) -> Path:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()

    return path


if __name__ == "__main__":
    print(create_database())
