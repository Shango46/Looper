import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import MAX_AGENTS_PER_COMPANY
from app.db.models import Agent, Company, Task


class LifecycleError(Exception):
    pass


async def get_active_ceo(session: AsyncSession, company_id: int) -> Agent | None:
    return (
        await session.execute(
            select(Agent).where(
                Agent.company_id == company_id, Agent.parent_agent_id.is_(None), Agent.status != "fired"
            )
        )
    ).scalars().first()


async def create_task_for_ceo(session: AsyncSession, company_id: int, instruction: str, origin: str = "user") -> Task:
    ceo = await get_active_ceo(session, company_id)
    if not ceo:
        raise LifecycleError("Company has no active CEO to receive instructions.")
    task = Task(company_id=company_id, target_agent_id=ceo.id, origin=origin, instruction=instruction, status="pending")
    session.add(task)
    await session.flush()
    return task


async def hire_agent(
    session: AsyncSession, company_id: int, parent_agent_id: int, name: str, title: str, personality: str, model_id: str
) -> Agent:
    company = await session.get(Company, company_id, options=[selectinload(Company.agents)])
    if not company:
        raise LifecycleError("Company not found")
    active_count = len([a for a in company.agents if a.status != "fired"])
    if active_count >= MAX_AGENTS_PER_COMPANY:
        raise LifecycleError(f"Maximum of {MAX_AGENTS_PER_COMPANY} agents per company reached.")

    parent = await session.get(Agent, parent_agent_id)
    if not parent or parent.company_id != company_id:
        raise LifecycleError("Invalid parent agent")
    if parent.status == "fired":
        raise LifecycleError("Cannot hire under a fired agent — replace that position first.")

    agent = Agent(
        company_id=company_id,
        parent_agent_id=parent_agent_id,
        name=name,
        title=title,
        personality=personality,
        model_id=model_id,
        status="active",
    )
    session.add(agent)
    await session.flush()
    return agent


async def fire_agent(session: AsyncSession, agent: Agent) -> None:
    agent.status = "fired"
    agent.fired_at = dt.datetime.now(dt.timezone.utc)


async def replace_agent(
    session: AsyncSession, fired_agent: Agent, name: str, title: str, personality: str, model_id: str
) -> Agent:
    if fired_agent.status != "fired":
        raise LifecycleError("Can only replace a fired agent")

    # Caller must have eager-loaded fired_agent.children (selectinload) before calling this.
    replacement = Agent(
        company_id=fired_agent.company_id,
        parent_agent_id=fired_agent.parent_agent_id,
        name=name,
        title=title,
        personality=personality,
        model_id=model_id,
        status="active",
    )
    session.add(replacement)
    await session.flush()

    for child in fired_agent.children:
        if child.status != "fired":
            child.parent_agent_id = replacement.id

    return replacement


async def edit_agent(session: AsyncSession, agent: Agent, name: str, title: str, personality: str, model_id: str) -> None:
    if agent.status == "fired":
        raise LifecycleError("Cannot edit a fired agent — replace it instead.")
    agent.name = name
    agent.title = title
    agent.personality = personality
    agent.model_id = model_id
