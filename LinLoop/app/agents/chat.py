from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.memory import record_memory
from app.db.models import Agent, Task

ACTIVE_STATUSES = ("pending", "in_progress", "awaiting_approval", "delegated")


class ChatBusyError(Exception):
    pass


class ChatAgentFiredError(Exception):
    pass


async def latest_chat_task(session: AsyncSession, agent_id: int) -> Task | None:
    return (
        await session.execute(
            select(Task)
            .where(Task.target_agent_id == agent_id, Task.origin == "chat")
            .order_by(Task.id.desc())
            .limit(1)
        )
    ).scalars().first()


async def send_message(session: AsyncSession, agent: Agent, message: str) -> int:
    """Appends to (or starts) the agent's chat thread. Returns the task_id to enqueue.
    Raises ChatAgentFiredError / ChatBusyError on invalid states — callers translate these
    into whatever error shape fits their transport (HTML HTTPException vs. JSON error body)."""
    if agent.status == "fired":
        raise ChatAgentFiredError(f"{agent.name} has been fired and cannot chat. Replace this position first.")

    task = await latest_chat_task(session, agent.id)
    if task and task.status in ACTIVE_STATUSES:
        raise ChatBusyError(f"{agent.name} is still responding — wait for that to finish first.")

    if task and task.status in ("completed", "failed", "cancelled"):
        messages = list(task.messages_json)
        messages.append({"role": "user", "content": message})
        task.messages_json = messages
        task.status = "pending"
        task.result = None
        await record_memory(session, agent.id, "user", message)
        return task.id

    new_task = Task(
        company_id=agent.company_id,
        target_agent_id=agent.id,
        origin="chat",
        instruction=message,
        status="pending",
    )
    session.add(new_task)
    await session.flush()
    return new_task.id
