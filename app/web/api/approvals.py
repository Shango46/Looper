from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.agents.approvals import resolve_approval
from app.db.models import Agent, ApprovalRequest, Task
from app.db.session import session_scope
from app.web.api.deps import get_authenticated_company_id

router = APIRouter()


async def _belongs_to_company(session, approval: ApprovalRequest, company_id: int) -> bool:
    if approval.kind == "risky_action" and approval.task_id:
        task = await session.get(Task, approval.task_id)
        return bool(task and task.company_id == company_id)
    if approval.kind == "skill_grant":
        agent_id = approval.payload_json.get("agent_id")
        agent = await session.get(Agent, agent_id) if agent_id else None
        return bool(agent and agent.company_id == company_id)
    return False


@router.get("/approvals")
async def list_approvals(company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        pending = (
            await session.execute(select(ApprovalRequest).where(ApprovalRequest.status == "pending"))
        ).scalars().all()
        mine = [a for a in pending if await _belongs_to_company(session, a, company_id)]
        return [
            {
                "id": a.id,
                "kind": a.kind,
                "task_id": a.task_id,
                "payload": a.payload_json,
                "created_at": a.created_at.isoformat(),
            }
            for a in mine
        ]


async def _resolve_scoped(approval_id: int, approve: bool, company_id: int) -> dict:
    async with session_scope() as session:
        approval = await session.get(ApprovalRequest, approval_id)
        if not approval or not await _belongs_to_company(session, approval, company_id):
            raise HTTPException(404, "Approval not found")
    await resolve_approval(approval_id, approve=approve)
    return {"ok": True}


@router.post("/approvals/{approval_id}/approve")
async def approve(approval_id: int, company_id: int = Depends(get_authenticated_company_id)):
    return await _resolve_scoped(approval_id, True, company_id)


@router.post("/approvals/{approval_id}/deny")
async def deny(approval_id: int, company_id: int = Depends(get_authenticated_company_id)):
    return await _resolve_scoped(approval_id, False, company_id)
