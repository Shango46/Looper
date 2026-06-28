import datetime as dt

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import Agent, Company, Heartbeat
from app.db.session import session_scope
from app.scheduler.heartbeats import compute_next_run
from app.web.templates_env import templates

router = APIRouter()

UNIT_SECONDS = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400}


@router.get("/companies/{company_id}/heartbeats")
async def list_heartbeats(request: Request, company_id: int):
    async with session_scope() as session:
        company = await session.get(Company, company_id, options=[selectinload(Company.agents)])
        if not company:
            raise HTTPException(404, "Company not found")
        heartbeats = (
            await session.execute(
                select(Heartbeat).where(Heartbeat.company_id == company_id).order_by(Heartbeat.id)
            )
        ).scalars().all()
        agents = [a for a in company.agents if a.status != "fired"]
        agent_names = {a.id: a.name for a in company.agents}
    return templates.TemplateResponse(
        "company_heartbeats.html",
        {
            "request": request,
            "company": company,
            "heartbeats": heartbeats,
            "agents": agents,
            "agent_names": agent_names,
        },
    )


@router.post("/companies/{company_id}/heartbeats")
async def create_heartbeat(
    company_id: int,
    name: str = Form(...),
    target_agent_id: str = Form(""),
    schedule_type: str = Form(...),
    interval_value: int = Form(0),
    interval_unit: str = Form("minutes"),
    once_at: str = Form(""),
    instruction_text: str = Form(...),
):
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")

        if schedule_type == "interval":
            seconds = max(interval_value, 1) * UNIT_SECONDS.get(interval_unit, 60)
            schedule_value = str(seconds)
        else:
            local_dt = dt.datetime.fromisoformat(once_at)
            aware = local_dt.astimezone() if local_dt.tzinfo is None else local_dt
            schedule_value = aware.astimezone(dt.timezone.utc).isoformat()

        hb = Heartbeat(
            company_id=company_id,
            agent_id=int(target_agent_id) if target_agent_id else None,
            name=name,
            schedule_type=schedule_type,
            schedule_value=schedule_value,
            instruction_text=instruction_text,
            enabled=True,
        )
        hb.next_run_at = compute_next_run(schedule_type, schedule_value)
        session.add(hb)

    return RedirectResponse(f"/companies/{company_id}/heartbeats", status_code=303)


@router.post("/heartbeats/{heartbeat_id}/toggle")
async def toggle_heartbeat(heartbeat_id: int):
    async with session_scope() as session:
        hb = await session.get(Heartbeat, heartbeat_id)
        if not hb:
            raise HTTPException(404, "Heartbeat not found")
        hb.enabled = not hb.enabled
        if hb.enabled and not hb.next_run_at:
            hb.next_run_at = compute_next_run(hb.schedule_type, hb.schedule_value)
        company_id = hb.company_id
    return RedirectResponse(f"/companies/{company_id}/heartbeats", status_code=303)


@router.post("/heartbeats/{heartbeat_id}/delete")
async def delete_heartbeat(heartbeat_id: int):
    async with session_scope() as session:
        hb = await session.get(Heartbeat, heartbeat_id)
        if not hb:
            raise HTTPException(404, "Heartbeat not found")
        company_id = hb.company_id
        await session.delete(hb)
    return RedirectResponse(f"/companies/{company_id}/heartbeats", status_code=303)
