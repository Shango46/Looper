from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import Company, Task
from app.db.session import session_scope
from app.web.api.deps import get_authenticated_company_id
from app.web.org_tree import TreeNode, build_org_tree

router = APIRouter()


def _serialize_node(node: TreeNode) -> dict:
    a = node.agent
    return {
        "id": a.id,
        "name": a.name,
        "title": a.title,
        "status": a.status,
        "model_id": a.model_id,
        "is_ceo": a.is_ceo,
        "children": [_serialize_node(c) for c in node.children],
    }


@router.get("/me")
async def me(company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        company = await session.get(Company, company_id, options=[selectinload(Company.agents)])
        if not company:
            raise HTTPException(404, "Company not found")
        tree = build_org_tree(company.agents)
        return {
            "id": company.id,
            "name": company.name,
            "paused": company.paused,
            "heartbeats_enabled": company.heartbeats_enabled,
            "spend_usd_total": company.spend_usd_total,
            "budget_usd_cap": company.budget_usd_cap,
            "org_tree": _serialize_node(tree) if tree else None,
            "agent_count": len(company.agents),
        }


@router.post("/pause")
async def pause(company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        company.paused = True
    return {"ok": True}


@router.post("/resume")
async def resume(company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        company.paused = False
        pending_tasks = (
            await session.execute(select(Task.id).where(Task.company_id == company_id, Task.status == "pending"))
        ).scalars().all()

    from app.worker import enqueue_task

    for tid in pending_tasks:
        await enqueue_task(tid)
    return {"ok": True}
