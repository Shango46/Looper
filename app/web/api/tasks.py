import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.agents.lifecycle import LifecycleError, create_task_for_ceo
from app.db.models import ApprovalRequest, Task
from app.db.session import session_scope
from app.web.api.deps import get_authenticated_company_id
from app.web.api.schemas import InstructRequest

router = APIRouter()


def _task_summary(t: Task) -> dict:
    return {
        "id": t.id,
        "status": t.status,
        "origin": t.origin,
        "target_agent_id": t.target_agent_id,
        "instruction": t.instruction,
        "result": t.result,
        "iterations": t.iterations,
        "updated_at": t.updated_at.isoformat(),
    }


@router.post("/instruct")
async def instruct(body: InstructRequest, company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        try:
            task = await create_task_for_ceo(session, company_id, body.instruction)
        except LifecycleError as e:
            raise HTTPException(400, str(e))
        task_id = task.id

    from app.worker import enqueue_task

    await enqueue_task(task_id)
    return {"ok": True, "task_id": task_id}


@router.get("/tasks")
async def list_tasks(limit: int = 50, company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        tasks = (
            await session.execute(
                select(Task).where(Task.company_id == company_id).order_by(Task.id.desc()).limit(limit)
            )
        ).scalars().all()
        return [_task_summary(t) for t in tasks]


@router.get("/tasks/{task_id}")
async def get_task(task_id: int, company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        task = await session.get(Task, task_id)
        if not task or task.company_id != company_id:
            raise HTTPException(404, "Task not found")
        data = _task_summary(task)
        data["messages"] = [
            {"role": m.get("role"), "content": m.get("content")}
            for m in task.messages_json
            if m.get("role") != "system"
        ]
        return data


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: int, company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        task = await session.get(Task, task_id)
        if not task or task.company_id != company_id:
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

    return {"ok": True}
