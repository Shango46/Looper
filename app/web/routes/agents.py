from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.agents.lifecycle import LifecycleError
from app.agents.lifecycle import edit_agent as edit_agent_lifecycle
from app.agents.lifecycle import fire_agent as fire_agent_lifecycle
from app.agents.lifecycle import replace_agent as replace_agent_lifecycle
from app.db.models import Agent, AgentExtraManager, AgentMemoryEntry, AgentTemplate, CachedModel, Company, Skill, SkillGrant
from app.db.session import session_scope
from app.web.templates_env import templates

router = APIRouter()


@router.get("/agents/{agent_id}")
async def agent_detail(request: Request, agent_id: int):
    async with session_scope() as session:
        agent = await session.get(
            Agent, agent_id, options=[
                selectinload(Agent.parent),
                selectinload(Agent.children),
                selectinload(Agent.extra_manager_links).selectinload(AgentExtraManager.manager),
            ]
        )
        if not agent:
            raise HTTPException(404, "Agent not found")
        company = await session.get(Company, agent.company_id)
        memory_count = (
            await session.execute(
                select(func.count()).select_from(AgentMemoryEntry).where(AgentMemoryEntry.agent_id == agent_id)
            )
        ).scalar_one()
        recent_memory = (
            await session.execute(
                select(AgentMemoryEntry)
                .where(AgentMemoryEntry.agent_id == agent_id)
                .order_by(AgentMemoryEntry.id.desc())
                .limit(50)
            )
        ).scalars().all()
        recent_memory = list(reversed(recent_memory))

        grants = (
            await session.execute(select(SkillGrant).where(SkillGrant.agent_id == agent_id))
        ).scalars().all()
        grant_rows = []
        for g in grants:
            skill = await session.get(Skill, g.skill_id)
            if skill:
                grant_rows.append((g, skill))

        owned_skills = (
            await session.execute(select(Skill).where(Skill.owner_agent_id == agent_id))
        ).scalars().all()

        granted_skill_ids = {g.skill_id for g, _ in grant_rows if g.status in ("approved", "requested")}

        shop_skills = (
            await session.execute(select(Skill).where(Skill.visibility == "shop").order_by(Skill.name))
        ).scalars().all()

        models = (
            await session.execute(select(CachedModel).order_by(CachedModel.supports_tools.desc(), CachedModel.name))
        ).scalars().all()

        agent_templates = (
            await session.execute(select(AgentTemplate).order_by(AgentTemplate.name))
        ).scalars().all()

    return templates.TemplateResponse(
        "agent_detail.html",
        {
            "request": request,
            "agent": agent,
            "company": company,
            "memory_count": memory_count,
            "recent_memory": recent_memory,
            "grant_rows": grant_rows,
            "owned_skills": owned_skills,
            "granted_skill_ids": granted_skill_ids,
            "shop_skills": shop_skills,
            "models": models,
            "agent_templates": agent_templates,
        },
    )


@router.post("/agents/{agent_id}/edit")
async def edit_agent(
    agent_id: int,
    name: str = Form(...),
    title: str = Form(...),
    personality: str = Form(""),
    model_id: str = Form(...),
):
    async with session_scope() as session:
        agent = await session.get(Agent, agent_id)
        if not agent:
            raise HTTPException(404, "Agent not found")
        try:
            await edit_agent_lifecycle(session, agent, name, title, personality, model_id)
        except LifecycleError as e:
            raise HTTPException(400, str(e))
    return RedirectResponse(f"/agents/{agent_id}", status_code=303)


@router.post("/agents/{agent_id}/fire")
async def fire_agent(agent_id: int):
    async with session_scope() as session:
        agent = await session.get(Agent, agent_id)
        if not agent:
            raise HTTPException(404, "Agent not found")
        await fire_agent_lifecycle(session, agent)
        company_id = agent.company_id
    return RedirectResponse(f"/companies/{company_id}", status_code=303)


@router.post("/agents/{agent_id}/replace")
async def replace_agent(
    agent_id: int,
    name: str = Form(...),
    title: str = Form(...),
    personality: str = Form(""),
    model_id: str = Form(...),
):
    async with session_scope() as session:
        fired_agent = await session.get(Agent, agent_id, options=[selectinload(Agent.children)])
        if not fired_agent:
            raise HTTPException(404, "Agent not found")
        try:
            await replace_agent_lifecycle(session, fired_agent, name, title, personality, model_id)
        except LifecycleError as e:
            raise HTTPException(400, str(e))
        company_id = fired_agent.company_id

    return RedirectResponse(f"/companies/{company_id}", status_code=303)
