import datetime as dt

from sqlalchemy import select

from app.agents.memory import record_memory
from app.db.models import Agent, Task
from app.db.session import session_scope

REPORT_TO_SUPERVISOR_SCHEMA = {
    "type": "function",
    "function": {
        "name": "report_to_supervisor",
        "description": "Send a status update, question, or escalation to your supervisor. Fire-and-forget — does not pause your current task.",
        "parameters": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    },
}


def build_delegate_schema(active_children: list[Agent]) -> dict:
    options = ", ".join(f"{c.id}={c.name} ({c.title})" for c in active_children)
    return {
        "type": "function",
        "function": {
            "name": "delegate_task",
            "description": (
                f"Delegate a task to one of your direct reports. Available: {options}. "
                "Your current task pauses until the subordinate finishes; their result is reported back to you."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_agent_id": {"type": "integer", "enum": [c.id for c in active_children]},
                    "instruction": {"type": "string"},
                },
                "required": ["target_agent_id", "instruction"],
            },
        },
    }


async def create_delegated_child_task(
    session, parent_task: Task, target_agent_id: int, instruction: str, tool_call_id: str
) -> Task | None:
    target = await session.get(Agent, target_agent_id)
    if not target or target.status == "fired" or target.parent_agent_id != parent_task.target_agent_id:
        return None
    child = Task(
        company_id=parent_task.company_id,
        target_agent_id=target_agent_id,
        parent_task_id=parent_task.id,
        origin="delegation",
        origin_tool_call_id=tool_call_id,
        instruction=instruction,
        status="pending",
    )
    session.add(child)
    await session.flush()
    return child


async def create_report_task(session, supervisor: Agent, company_id: int, message: str) -> Task:
    task = Task(
        company_id=company_id,
        target_agent_id=supervisor.id,
        origin="report",
        instruction=message,
        status="pending",
    )
    session.add(task)
    await session.flush()
    return task


async def on_task_finished(task_id: int) -> None:
    """Hook run after a task reaches completed/failed. Reports the result back to a delegating
    parent task (if any) and resumes it once all of its delegated children are done."""
    resume_task_id = None
    async with session_scope() as session:
        child = await session.get(Task, task_id)
        if not child or not child.parent_task_id:
            return
        parent = await session.get(Task, child.parent_task_id)
        if not parent or not child.origin_tool_call_id:
            return

        sub_agent = await session.get(Agent, child.target_agent_id)
        summary = (
            f"Subordinate {sub_agent.name if sub_agent else child.target_agent_id} "
            f"{child.status}: {child.result or '(no result)'}"
        )
        messages = list(parent.messages_json)
        messages.append(
            {"role": "tool", "tool_call_id": child.origin_tool_call_id, "name": "delegate_task", "content": summary}
        )
        parent.messages_json = messages
        parent.updated_at = dt.datetime.now(dt.timezone.utc)
        await record_memory(session, parent.target_agent_id, "tool", summary)

        still_pending = (
            await session.execute(
                select(Task).where(
                    Task.parent_task_id == parent.id, Task.status.not_in(["completed", "failed"])
                )
            )
        ).scalars().all()

        if not still_pending and parent.status == "delegated":
            parent.status = "pending"
            resume_task_id = parent.id

    if resume_task_id:
        from app.worker import enqueue_task

        await enqueue_task(resume_task_id)
