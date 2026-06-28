import asyncio
import datetime as dt
import logging

from sqlalchemy import select

from app.config import HEARTBEAT_POLL_INTERVAL_SECONDS
from app.db.models import Agent, Company, Heartbeat, Task
from app.db.session import session_scope
from app.worker import enqueue_task

logger = logging.getLogger("looper.scheduler.heartbeats")

_poll_task: asyncio.Task | None = None


def compute_next_run(schedule_type: str, schedule_value: str, base: dt.datetime | None = None) -> dt.datetime | None:
    base = base or dt.datetime.now(dt.timezone.utc)
    if schedule_type == "interval":
        return base + dt.timedelta(seconds=int(schedule_value))
    if schedule_type == "once":
        return dt.datetime.fromisoformat(schedule_value)
    return None


async def _fire(heartbeat: Heartbeat, session) -> None:
    company = await session.get(Company, heartbeat.company_id)
    target_agent_id = heartbeat.agent_id
    if not target_agent_id:
        ceo = (
            await session.execute(
                select(Agent).where(Agent.company_id == heartbeat.company_id, Agent.parent_agent_id.is_(None))
            )
        ).scalars().first()
        target_agent_id = ceo.id if ceo else None
    if not target_agent_id:
        logger.warning("Heartbeat %s has no resolvable target agent, skipping", heartbeat.id)
        return

    target_agent = await session.get(Agent, target_agent_id)
    if not target_agent or target_agent.status == "fired":
        logger.warning("Heartbeat %s targets a fired/missing agent, skipping this run", heartbeat.id)
        now = dt.datetime.now(dt.timezone.utc)
        heartbeat.last_run_at = now
        if heartbeat.schedule_type == "once":
            heartbeat.enabled = False
            heartbeat.next_run_at = None
        else:
            heartbeat.next_run_at = compute_next_run(heartbeat.schedule_type, heartbeat.schedule_value, base=now)
        return

    task = Task(
        company_id=heartbeat.company_id,
        target_agent_id=target_agent_id,
        origin="heartbeat",
        instruction=heartbeat.instruction_text,
        status="pending",
    )
    session.add(task)
    await session.flush()
    await enqueue_task(task.id)

    now = dt.datetime.now(dt.timezone.utc)
    heartbeat.last_run_at = now
    if heartbeat.schedule_type == "once":
        heartbeat.enabled = False
        heartbeat.next_run_at = None
    else:
        heartbeat.next_run_at = compute_next_run(heartbeat.schedule_type, heartbeat.schedule_value, base=now)


async def _tick() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    async with session_scope() as session:
        due = (
            await session.execute(
                select(Heartbeat).where(Heartbeat.enabled.is_(True), Heartbeat.next_run_at <= now)
            )
        ).scalars().all()
        for hb in due:
            company = await session.get(Company, hb.company_id)
            if not company or not company.heartbeats_enabled or company.paused:
                continue
            try:
                await _fire(hb, session)
            except Exception:
                logger.exception("Heartbeat %s failed to fire", hb.id)


async def _poll_loop() -> None:
    while True:
        try:
            await _tick()
        except Exception:
            logger.exception("Heartbeat poll tick failed")
        await asyncio.sleep(HEARTBEAT_POLL_INTERVAL_SECONDS)


def start_heartbeat_scheduler() -> None:
    global _poll_task
    _poll_task = asyncio.create_task(_poll_loop())


async def stop_heartbeat_scheduler() -> None:
    global _poll_task
    if _poll_task:
        _poll_task.cancel()
        try:
            await _poll_task
        except asyncio.CancelledError:
            pass
        _poll_task = None
