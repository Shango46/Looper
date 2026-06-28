import datetime as dt

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.db.models import McpServer
from app.db.session import session_scope
from app.mcp.client import McpToolError, discover_tools

router = APIRouter()


def _parse_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _parse_env(text: str) -> dict:
    env = {}
    for line in _parse_lines(text):
        if "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


@router.post("/companies/{company_id}/mcp-servers")
async def create_mcp_server(
    company_id: int,
    name: str = Form(...),
    transport: str = Form(...),
    command: str = Form(""),
    args: str = Form(""),
    url: str = Form(""),
    env: str = Form(""),
):
    if transport not in ("stdio", "streamable_http"):
        raise HTTPException(400, "Invalid transport")
    async with session_scope() as session:
        session.add(
            McpServer(
                company_id=company_id,
                name=name,
                transport=transport,
                command=command.strip() or None,
                args_json=_parse_lines(args) or None,
                url=url.strip() or None,
                env_json=_parse_env(env) or None,
                enabled=True,
            )
        )
    return RedirectResponse(f"/companies/{company_id}/settings", status_code=303)


@router.post("/mcp-servers/{server_id}/refresh")
async def refresh_mcp_server(server_id: int):
    async with session_scope() as session:
        server = await session.get(McpServer, server_id)
        if not server:
            raise HTTPException(404, "MCP server not found")
        company_id = server.company_id
        try:
            tools = await discover_tools(server)
            server.cached_tools_json = tools
            server.tools_refreshed_at = dt.datetime.now(dt.timezone.utc)
        except McpToolError as e:
            raise HTTPException(400, str(e))
    return RedirectResponse(f"/companies/{company_id}/settings", status_code=303)


@router.post("/mcp-servers/{server_id}/toggle")
async def toggle_mcp_server(server_id: int):
    async with session_scope() as session:
        server = await session.get(McpServer, server_id)
        if not server:
            raise HTTPException(404, "MCP server not found")
        server.enabled = not server.enabled
        company_id = server.company_id
    return RedirectResponse(f"/companies/{company_id}/settings", status_code=303)


@router.post("/mcp-servers/{server_id}/delete")
async def delete_mcp_server(server_id: int):
    async with session_scope() as session:
        server = await session.get(McpServer, server_id)
        if not server:
            raise HTTPException(404, "MCP server not found")
        company_id = server.company_id
        await session.delete(server)
    return RedirectResponse(f"/companies/{company_id}/settings", status_code=303)
