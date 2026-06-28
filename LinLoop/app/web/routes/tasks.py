import datetime as dt

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.db.models import Agent, ApprovalRequest, Task
from app.db.session import session_scope
from app.web.templates_env import templates

router = APIRouter()


@router.get("/tasks/{task_id}")
async def task_detail(request: Request, task_id: int):
    async with session_scope() as session:
        task = await session.get(Task, task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        agent = await session.get(Agent, task.target_agent_id)
    live = task.status in ("pending", "in_progress", "delegated", "awaiting_approval")
    return templates.TemplateResponse(
        "task_detail.html",
        {"request": request, "task": task, "agent": agent, "live": live},
    )


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: int):
    async with session_scope() as session:
        task = await session.get(Task, task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        if task.status not in ("completed", "failed", "cancelled"):
            task.status = "cancelled"
            task.result = "Cancelled by user."

        stale_approvals = (
            await session.execute(
                select(ApprovalRequest).where(ApprovalRequest.task_id == task_id, ApprovalRequest.status == "pending")
            )
        ).scalars().all()
        for a in stale_approvals:
            a.status = "denied"
            a.resolved_at = dt.datetime.now(dt.timezone.utc)

    return RedirectResponse(f"/tasks/{task_id}", status_code=303)
