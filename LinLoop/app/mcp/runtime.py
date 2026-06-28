import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import McpServer

_INVALID_NAME_CHARS = re.compile(r"[^a-zA-Z0-9_-]")


def namespaced_tool_name(server_id: int, original_name: str) -> str:
    safe = _INVALID_NAME_CHARS.sub("_", original_name)
    return f"mcp_{server_id}_{safe}"


async def build_mcp_context(session: AsyncSession, company_id: int) -> dict:
    """Returns dynamic tool schemas for every enabled MCP server's cached tool list, plus a
    tool_map for dispatch: {namespaced_name: (server_id, original_name)}."""
    servers = (
        await session.execute(
            select(McpServer).where(McpServer.company_id == company_id, McpServer.enabled.is_(True))
        )
    ).scalars().all()

    schemas: list[dict] = []
    tool_map: dict[str, tuple[int, str]] = {}

    for server in servers:
        for tool in server.cached_tools_json or []:
            name = namespaced_tool_name(server.id, tool["name"])
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": f"[MCP: {server.name}] {tool.get('description', '')}",
                        "parameters": tool.get("input_schema") or {"type": "object", "properties": {}},
                    },
                }
            )
            tool_map[name] = (server.id, tool["name"])

    return {"schemas": schemas, "tool_map": tool_map}
