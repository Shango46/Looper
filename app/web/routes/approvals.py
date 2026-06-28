from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.agents.approvals import resolve_approval
from app.db.models import Agent, ApprovalRequest, Skill, SkillGrant, Task
from app.db.session import session_scope
from app.web.templates_env import templates

router = APIRouter()


@router.get("/approvals")
async def approvals_inbox(request: Request):
    async with session_scope() as session:
        pending = (
            await session.execute(
                select(ApprovalRequest).where(ApprovalRequest.status == "pending").order_by(ApprovalRequest.id)
            )
        ).scalars().all()
        resolved = (
            await session.execute(
                select(ApprovalRequest)
                .where(ApprovalRequest.status != "pending")
                .order_by(ApprovalRequest.id.desc())
                .limit(20)
            )
        ).scalars().all()

        task_ids = {a.task_id for a in pending + resolved if a.task_id}
        tasks = {}
        agent_names = {}
        for tid in task_ids:
            t = await session.get(Task, tid)
            if t:
                tasks[tid] = t
                agent = await session.get(Agent, t.target_agent_id)
                if agent:
                    agent_names[tid] = agent.name

        skills = {}
        for a in pending:
            if a.kind == "skill_grant":
                grant = await session.get(SkillGrant, a.payload_json.get("skill_grant_id"))
                if grant:
                    skill = await session.get(Skill, grant.skill_id)
                    if skill:
                        skills[a.payload_json["skill_grant_id"]] = skill

    return templates.TemplateResponse(
        "approvals.html",
        {
            "request": request,
            "pending": pending,
            "resolved": resolved,
            "tasks": tasks,
            "agent_names": agent_names,
            "skills": skills,
        },
    )


@router.post("/approvals/{approval_id}/approve")
async def approve(approval_id: int):
    await resolve_approval(approval_id, approve=True)
    return RedirectResponse("/approvals", status_code=303)


@router.post("/approvals/{approval_id}/deny")
async def deny(approval_id: int):
    await resolve_approval(approval_id, approve=False)
    return RedirectResponse("/approvals", status_code=303)


@router.get("/approvals/pending-count")
async def pending_count():
    async with session_scope() as session:
        count = (
            await session.execute(select(ApprovalRequest).where(ApprovalRequest.status == "pending"))
        ).scalars().all()
    return {"count": len(count)}
