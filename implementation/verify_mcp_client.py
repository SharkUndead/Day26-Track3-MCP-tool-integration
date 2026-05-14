from __future__ import annotations

import asyncio

from fastmcp import Client

try:
    from . import mcp_server
except ImportError:
    import mcp_server


async def main() -> None:
    async with Client(mcp_server.mcp) as client:
        tools = await client.list_tools()
        tool_names = sorted(tool.name for tool in tools)
        assert tool_names == ["aggregate", "insert", "search"], f"Unexpected tools: {tool_names}"

        resources = await client.list_resources()
        resource_uris = [str(resource.uri) for resource in resources]
        assert "schema://database" in resource_uris, f"Missing database resource: {resource_uris}"

        templates = await client.list_resource_templates()
        template_uris = [str(template.uriTemplate) for template in templates]
        assert "schema://table/{table_name}" in template_uris, f"Missing table template: {template_uris}"

        search_result = await client.call_tool(
            "search",
            {"table": "students", "filters": {"cohort": "A1"}},
        )
        assert search_result.data["ok"] is True
        assert search_result.data["count"] >= 2
        assert all(row["cohort"] == "A1" for row in search_result.data["rows"])

        invalid_result = await client.call_tool("search", {"table": "missing_table"})
        assert invalid_result.data["ok"] is False
        assert "Unknown table" in invalid_result.data["error"]

        schema_result = await client.read_resource("schema://database")
        assert "students" in schema_result[0].text

        print(
            {
                "ok": True,
                "tools": tool_names,
                "resources": resource_uris,
                "resource_templates": template_uris,
            }
        )


if __name__ == "__main__":
    asyncio.run(main())
