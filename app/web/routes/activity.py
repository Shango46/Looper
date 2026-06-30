from fastapi import APIRouter, Request
from sqlalchemy import select

from app.db.models import Agent, AgentMemoryEntry
from app.db.session import session_scope
from app.web.templates_env import templates

router = APIRouter()


@router.get("/companies/{company_id}/activity")
async def activity_page(request: Request, company_id: int, agent_id: int | None = None):
    async with session_scope() as session:
        agents = (
            await session.execute(
                select(Agent)
                .where(Agent.company_id == company_id, Agent.status != "fired")
                .order_by(Agent.id)
            )
        ).scalars().all()
    return templates.TemplateResponse("company_activity.html", {
        "request": request,
        "company_id": company_id,
        "agents": agents,
        "agent_id": agent_id,
    })


@router.get("/companies/{company_id}/activity/feed")
async def activity_feed(request: Request, company_id: int, agent_id: int | None = None):
    async with session_scope() as session:
        q = (
            select(AgentMemoryEntry, Agent.name.label("agent_name"))
            .join(Agent, AgentMemoryEntry.agent_id == Agent.id)
            .where(Agent.company_id == company_id)
        )
        if agent_id:
            q = q.where(AgentMemoryEntry.agent_id == agent_id)
        q = q.order_by(AgentMemoryEntry.id.desc()).limit(150)
        rows = (await session.execute(q)).all()

    entries = [
        {
            "id": row.AgentMemoryEntry.id,
            "agent_name": row.agent_name,
            "agent_id": row.AgentMemoryEntry.agent_id,
            "role": row.AgentMemoryEntry.role,
            "content": row.AgentMemoryEntry.content,
            "created_at": row.AgentMemoryEntry.created_at,
        }
        for row in rows
    ]
    return templates.TemplateResponse("_activity_feed.html", {
        "request": request,
        "entries": entries,
        "company_id": company_id,
    })
