from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.agents.chat import ACTIVE_STATUSES, ChatAgentFiredError, ChatBusyError, latest_chat_task, send_message
from app.agents.lifecycle import LifecycleError
from app.agents.lifecycle import edit_agent as edit_agent_lifecycle
from app.agents.lifecycle import fire_agent as fire_agent_lifecycle
from app.agents.lifecycle import hire_agent as hire_agent_lifecycle
from app.agents.lifecycle import replace_agent as replace_agent_lifecycle
from app.db.models import Agent, AgentExtraManager, Skill, SkillGrant
from app.db.session import session_scope
from app.web.api.deps import get_authenticated_company_id
from app.web.api.schemas import EditAgentRequest, HireAgentRequest, ChatMessageRequest, ReplaceAgentRequest

router = APIRouter()


async def _get_owned_agent(session, company_id: int, agent_id: int, **get_kwargs) -> Agent:
    agent = await session.get(Agent, agent_id, **get_kwargs)
    if not agent or agent.company_id != company_id:
        raise HTTPException(404, "Agent not found")
    return agent


def _agent_summary(a: Agent) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "title": a.title,
        "personality": a.personality,
        "status": a.status,
        "model_id": a.model_id,
        "parent_agent_id": a.parent_agent_id,
        "is_ceo": a.is_ceo,
    }


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: int, company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        agent = await _get_owned_agent(session, company_id, agent_id, options=[
            selectinload(Agent.children),
            selectinload(Agent.extra_manager_links).selectinload(AgentExtraManager.manager),
        ])
        children = [{"id": c.id, "name": c.name, "status": c.status} for c in agent.children if c.status != "fired"]
        extra_managers = [
            {"id": link.manager.id, "name": link.manager.name, "title": link.manager.title}
            for link in agent.extra_manager_links
        ]

        grants = (await session.execute(select(SkillGrant).where(SkillGrant.agent_id == agent_id))).scalars().all()
        skills = []
        for g in grants:
            skill = await session.get(Skill, g.skill_id)
            if skill:
                skills.append({"id": skill.id, "name": skill.name, "status": g.status, "grant_id": g.id})

        data = _agent_summary(agent)
        data["children"] = children
        data["extra_managers"] = extra_managers
        data["skills"] = skills
        return data


@router.post("/agents")
async def hire(body: HireAgentRequest, company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        try:
            agent = await hire_agent_lifecycle(
                session, company_id, body.parent_agent_id, body.name, body.title, body.personality, body.model_id
            )
        except LifecycleError as e:
            raise HTTPException(400, str(e))
        return _agent_summary(agent)


@router.post("/agents/{agent_id}/edit")
async def edit(agent_id: int, body: EditAgentRequest, company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        agent = await _get_owned_agent(session, company_id, agent_id)
        try:
            await edit_agent_lifecycle(session, agent, body.name, body.title, body.personality, body.model_id)
        except LifecycleError as e:
            raise HTTPException(400, str(e))
        return _agent_summary(agent)


@router.post("/agents/{agent_id}/fire")
async def fire(agent_id: int, company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        agent = await _get_owned_agent(session, company_id, agent_id)
        await fire_agent_lifecycle(session, agent)
        return {"ok": True}


@router.post("/agents/{agent_id}/replace")
async def replace(agent_id: int, body: ReplaceAgentRequest, company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        fired_agent = await _get_owned_agent(session, company_id, agent_id, options=[selectinload(Agent.children)])
        try:
            replacement = await replace_agent_lifecycle(
                session, fired_agent, body.name, body.title, body.personality, body.model_id
            )
        except LifecycleError as e:
            raise HTTPException(400, str(e))
        return _agent_summary(replacement)


@router.get("/agents/{agent_id}/chat")
async def get_chat(agent_id: int, company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        agent = await _get_owned_agent(session, company_id, agent_id)
        task = await latest_chat_task(session, agent_id)
        busy = bool(task and task.status in ACTIVE_STATUSES)
        messages = [
            {"role": m["role"], "content": m.get("content")}
            for m in (task.messages_json if task else [])
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]
        return {"agent_id": agent_id, "busy": busy, "messages": messages}


@router.post("/agents/{agent_id}/chat")
async def post_chat(agent_id: int, body: ChatMessageRequest, company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        agent = await _get_owned_agent(session, company_id, agent_id)
        try:
            task_id = await send_message(session, agent, body.message)
        except ChatAgentFiredError as e:
            raise HTTPException(400, str(e))
        except ChatBusyError as e:
            raise HTTPException(409, str(e))

    from app.worker import enqueue_task

    await enqueue_task(task_id)
    return {"ok": True, "task_id": task_id}
