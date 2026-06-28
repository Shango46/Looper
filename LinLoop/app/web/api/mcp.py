import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.db.models import McpServer
from app.db.session import session_scope
from app.mcp.client import McpToolError, discover_tools
from app.web.api.deps import get_authenticated_company_id

router = APIRouter()


class CreateMcpServerRequest(BaseModel):
    name: str
    transport: str
    command: str | None = None
    args: list[str] = []
    url: str | None = None
    env: dict[str, str] = {}


def _server_summary(s: McpServer) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "transport": s.transport,
        "enabled": s.enabled,
        "tool_count": len(s.cached_tools_json or []),
        "tools_refreshed_at": s.tools_refreshed_at.isoformat() if s.tools_refreshed_at else None,
    }


@router.get("/mcp-servers")
async def list_mcp_servers(company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        rows = (await session.execute(select(McpServer).where(McpServer.company_id == company_id))).scalars().all()
        return [_server_summary(s) for s in rows]


@router.post("/mcp-servers")
async def create_mcp_server(body: CreateMcpServerRequest, company_id: int = Depends(get_authenticated_company_id)):
    if body.transport not in ("stdio", "streamable_http"):
        raise HTTPException(400, "Invalid transport")
    async with session_scope() as session:
        server = McpServer(
            company_id=company_id,
            name=body.name,
            transport=body.transport,
            command=body.command,
            args_json=body.args or None,
            url=body.url,
            env_json=body.env or None,
            enabled=True,
        )
        session.add(server)
        await session.flush()
        return _server_summary(server)


async def _get_owned_server(session, company_id: int, server_id: int) -> McpServer:
    server = await session.get(McpServer, server_id)
    if not server or server.company_id != company_id:
        raise HTTPException(404, "MCP server not found")
    return server


@router.post("/mcp-servers/{server_id}/refresh")
async def refresh_mcp_server(server_id: int, company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        server = await _get_owned_server(session, company_id, server_id)
        try:
            tools = await discover_tools(server)
        except McpToolError as e:
            raise HTTPException(400, str(e))
        server.cached_tools_json = tools
        server.tools_refreshed_at = dt.datetime.now(dt.timezone.utc)
        return _server_summary(server)


@router.post("/mcp-servers/{server_id}/toggle")
async def toggle_mcp_server(server_id: int, company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        server = await _get_owned_server(session, company_id, server_id)
        server.enabled = not server.enabled
        return _server_summary(server)


@router.post("/mcp-servers/{server_id}/delete")
async def delete_mcp_server(server_id: int, company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        server = await _get_owned_server(session, company_id, server_id)
        await session.delete(server)
    return {"ok": True}
