# Day26 Track 3: SQLite MCP Tool Integration

This project implements a local Model Context Protocol server with FastMCP and SQLite. It exposes three tools (`search`, `insert`, `aggregate`) and two schema resources (`schema://database`, `schema://table/{table_name}`).

## Project Structure

```text
implementation/
  db.py                         SQLite adapter, validation, safe SQL builders
  init_db.py                    Reproducible schema and seed data
  mcp_server.py                 FastMCP tools and resources
  verify_server.py              Repeatable smoke verification
  sqlite_lab.db                 Generated local database after initialization
  client-configs/
    claude-mcp.json
    codex-config.toml
    gemini-command.txt
  tests/
    test_db.py
pseudocode/                     Original lab starter pseudocode
requirements.txt
Rubric.md
Tips.md
```

## Setup

```bash
python -m pip install -r requirements.txt
python implementation/init_db.py
```

The init script creates `implementation/sqlite_lab.db` with:

- `students`
- `courses`
- `enrollments`

## Run the MCP Server

```bash
python implementation/mcp_server.py
```

The server runs on stdio by default, which is the simplest transport for local MCP clients.

## Tools

### `search`

Search rows in a table with optional selected columns, filters, ordering, limit, and offset.

Example arguments:

```json
{
  "table": "students",
  "filters": {
    "cohort": "A1"
  },
  "columns": ["id", "name", "cohort", "gpa"],
  "limit": 20,
  "order_by": "gpa",
  "descending": true
}
```

Supported filter operators:

- `eq`
- `ne`
- `gt`
- `gte`
- `lt`
- `lte`
- `like`
- `in`

Filter shorthand uses equality:

```json
{
  "cohort": "A1"
}
```

Explicit operators are also supported:

```json
{
  "gpa": {
    "gte": 3.5
  }
}
```

### `insert`

Insert one row into a table.

Example arguments:

```json
{
  "table": "students",
  "values": {
    "name": "Lan Do",
    "cohort": "C3",
    "email": "lan.do@example.edu",
    "gpa": 3.55
  }
}
```

### `aggregate`

Run aggregate metrics with optional filters and grouping.

Supported metrics:

- `count`
- `avg`
- `sum`
- `min`
- `max`

Example arguments:

```json
{
  "table": "students",
  "metric": "avg",
  "column": "gpa",
  "group_by": "cohort"
}
```

## Resources

Full database schema:

```text
schema://database
```

Single table schema:

```text
schema://table/students
```

## Verification

Run the repeatable smoke check:

```bash
python implementation/verify_server.py
```

Expected checks:

- database initializes
- full schema is readable
- table schema is readable
- `search` works
- `insert` works
- `aggregate` works
- invalid requests are rejected

Run automated tests:

```bash
pytest
```

Run an MCP-level smoke check with FastMCP's in-process client:

```bash
python implementation/verify_mcp_client.py
```

## MCP Inspector

One common local Inspector command is:

```bash
npx -y @modelcontextprotocol/inspector python "D:/VinUni_proJect_day/day 26/Day26-Track3-MCP-tool-integration/implementation/mcp_server.py"
```

Verify in Inspector:

- tools appear: `search`, `insert`, `aggregate`
- resources appear: `schema://database`, `schema://table/{table_name}`
- a valid search call succeeds
- an invalid call, such as table `missing_table`, returns a clear error

## Client Examples

Client configuration examples are in `implementation/client-configs/`.

Codex config fragment:

```toml
[mcp_servers.sqlite_lab]
command = "python"
args = ["D:/VinUni_proJect_day/day 26/Day26-Track3-MCP-tool-integration/implementation/mcp_server.py"]
```

Claude `.mcp.json` fragment:

```json
{
  "mcpServers": {
    "sqlite-lab": {
      "type": "stdio",
      "command": "python",
      "args": [
        "D:/VinUni_proJect_day/day 26/Day26-Track3-MCP-tool-integration/implementation/mcp_server.py"
      ],
      "env": {}
    }
  }
}
```

Gemini CLI command:

```bash
gemini mcp add sqlite-lab python "D:/VinUni_proJect_day/day 26/Day26-Track3-MCP-tool-integration/implementation/mcp_server.py" --description "SQLite lab FastMCP server" --timeout 10000
```

## Demo Checklist

For the final submission, record a short video of about two minutes showing:

1. `python implementation/verify_server.py` passing.
2. MCP Inspector or one MCP client connected to the server.
3. `search` students in cohort `A1`.
4. `insert` a new student.
5. `aggregate` average GPA by cohort.
6. Read `schema://database` or `schema://table/students`.
7. Show one invalid request returning a clear error.
