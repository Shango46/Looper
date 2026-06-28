import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.db.models import Agent, Skill, SkillGrant
from app.db.session import session_scope
from app.skills.export import create_skill_for_agent
from app.web.api.deps import get_authenticated_company_id
from app.web.api.schemas import CreateSkillRequest, GrantSkillRequest

router = APIRouter()


def _skill_summary(s: Skill) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "visibility": s.visibility,
        "has_custom_tool": bool(s.custom_tool_source),
    }


@router.get("/skills")
async def list_skills(company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        own = (
            await session.execute(
                select(Skill).where(Skill.company_id == company_id, Skill.visibility != "shop")
            )
        ).scalars().all()
        shop = (await session.execute(select(Skill).where(Skill.visibility == "shop"))).scalars().all()
        return {"own": [_skill_summary(s) for s in own], "shop": [_skill_summary(s) for s in shop]}


@router.post("/skills")
async def create_skill(body: CreateSkillRequest, company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        agent = await session.get(Agent, body.agent_id)
        if not agent or agent.company_id != company_id:
            raise HTTPException(404, "Agent not found")
        skill = await create_skill_for_agent(
            session, agent, body.name, body.description, body.instructions_md,
            body.custom_tool_source, body.custom_tool_schema_json, body.visibility,
        )
        return _skill_summary(skill)


@router.post("/skills/{skill_id}/grant")
async def grant_skill(skill_id: int, body: GrantSkillRequest, company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        skill = await session.get(Skill, skill_id)
        if not skill:
            raise HTTPException(404, "Skill not found")
        agent = await session.get(Agent, body.agent_id)
        if not agent or agent.company_id != company_id:
            raise HTTPException(404, "Agent not found")

        existing = (
            await session.execute(
                select(SkillGrant).where(SkillGrant.skill_id == skill_id, SkillGrant.agent_id == body.agent_id)
            )
        ).scalars().first()
        if existing:
            existing.status = "approved"
            existing.resolved_at = dt.datetime.now(dt.timezone.utc)
        else:
            session.add(
                SkillGrant(
                    skill_id=skill_id, agent_id=body.agent_id, status="approved",
                    resolved_at=dt.datetime.now(dt.timezone.utc),
                )
            )
    return {"ok": True}
