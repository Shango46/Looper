import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Agent, Skill, SkillGrant

EXPORT_VERSION = 1


async def grant_owner_access(session: AsyncSession, skill: Skill, agent_id: int) -> None:
    """The agent that creates/imports a skill gets automatic, pre-approved access to it."""
    session.add(
        SkillGrant(skill_id=skill.id, agent_id=agent_id, status="approved", resolved_at=dt.datetime.now(dt.timezone.utc))
    )


async def create_skill_for_agent(
    session: AsyncSession,
    agent: Agent,
    name: str,
    description: str,
    instructions_md: str,
    custom_tool_source: str | None,
    custom_tool_schema_json: dict | None,
    visibility: str,
) -> Skill:
    skill = Skill(
        name=name,
        description=description,
        instructions_md=instructions_md,
        custom_tool_source=custom_tool_source or None,
        custom_tool_schema_json=custom_tool_schema_json,
        visibility=visibility,
        company_id=agent.company_id,
        owner_agent_id=agent.id,
    )
    session.add(skill)
    await session.flush()
    await grant_owner_access(session, skill, agent.id)
    return skill


def to_export_dict(skill: Skill) -> dict:
    return {
        "looper_skill_export_version": EXPORT_VERSION,
        "name": skill.name,
        "description": skill.description,
        "instructions_md": skill.instructions_md,
        "custom_tool_source": skill.custom_tool_source,
        "custom_tool_schema_json": skill.custom_tool_schema_json,
    }


def from_export_dict(data: dict) -> dict:
    return {
        "name": data.get("name", "Imported Skill"),
        "description": data.get("description", ""),
        "instructions_md": data.get("instructions_md", ""),
        "custom_tool_source": data.get("custom_tool_source"),
        "custom_tool_schema_json": data.get("custom_tool_schema_json"),
    }
