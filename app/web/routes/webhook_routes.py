"""Inbound webhooks — lets external systems (n8n, Zapier, etc.) trigger agent tasks."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.db.models import Agent, Company, Task
from app.db.session import session_scope

router = APIRouter()


@router.post("/webhook/{token}")
async def inbound_webhook(token: str, request: Request):
    """Receive a webhook and create a task for the company's CEO.

    Expected JSON body:
        {
          "instruction": "What you want the agent to do",
          "target_agent_id": 42   // optional — defaults to CEO
        }

    Returns:
        {"ok": true, "task_id": N}
    """
    async with session_scope() as session:
        result = await session.execute(
            select(Company).where(Company.webhook_secret == token)
        )
        company = result.scalars().first()
        if not company:
            raise HTTPException(status_code=401, detail="Invalid webhook token.")
        if company.paused:
            raise HTTPException(status_code=503, detail="Company is paused.")

        # Parse body
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Request body must be valid JSON.")

        instruction = (body.get("instruction") or "").strip()
        if not instruction:
            raise HTTPException(status_code=400, detail="'instruction' field is required and must not be empty.")

        target_agent_id = body.get("target_agent_id")

        if target_agent_id:
            agent = await session.get(Agent, int(target_agent_id))
            if not agent or agent.company_id != company.id or agent.status == "fired":
                raise HTTPException(status_code=400, detail="Invalid or fired target_agent_id.")
        else:
            # Default to CEO (root agent)
            ceo_result = await session.execute(
                select(Agent).where(
                    Agent.company_id == company.id,
                    Agent.parent_agent_id.is_(None),
                    Agent.status != "fired",
                )
            )
            agent = ceo_result.scalars().first()
            if not agent:
                raise HTTPException(status_code=503, detail="No active CEO agent found for this company.")

        task = Task(
            company_id=company.id,
            target_agent_id=agent.id,
            origin="user",
            instruction=instruction,
            status="pending",
        )
        session.add(task)
        await session.flush()
        task_id = task.id

    from app.worker import enqueue_task
    await enqueue_task(task_id)

    return JSONResponse({"ok": True, "task_id": task_id})


@router.post("/companies/{company_id}/webhook/generate")
async def generate_webhook_token(company_id: int):
    """Generate (or regenerate) a webhook secret for a company."""
    token = secrets.token_hex(24)
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")
        company.webhook_secret = token
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/companies/{company_id}/settings#webhook", status_code=303)


@router.post("/companies/{company_id}/webhook/revoke")
async def revoke_webhook_token(company_id: int):
    """Remove the webhook secret, disabling inbound webhooks for this company."""
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")
        company.webhook_secret = None
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/companies/{company_id}/settings#webhook", status_code=303)
