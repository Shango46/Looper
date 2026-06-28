import asyncio
import logging

from sqlalchemy import select

from app.agents.loop import run_step
from app.config import WORKER_CONCURRENCY
from app.db.models import Company, Task
from app.db.session import session_scope

logger = logging.getLogger("looper.worker")

_queue: asyncio.Queue[int] | None = None
_busy_companies: set[int] = set()
_worker_tasks: list[asyncio.Task] = []
_requeue_delay = 0.5


def _get_queue() -> asyncio.Queue:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue()
    return _queue


async def enqueue_task(task_id: int) -> None:
    await _get_queue().put(task_id)


async def _worker_loop(worker_name: str) -> None:
    queue = _get_queue()
    while True:
        task_id = await queue.get()
        async with session_scope() as session:
            task = await session.get(Task, task_id)
            # awaiting_approval/delegated tasks are resumed explicitly (phase 4/5), not by plain dequeue
            if not task or task.status in ("completed", "failed", "cancelled", "awaiting_approval", "delegated"):
                queue.task_done()
                continue
            company_id = task.company_id
            company = await session.get(Company, company_id)
            if company and company.paused:
                # Dropped, not requeued — a paused company only resumes processing via the explicit
                # "Resume" action, which re-enqueues its pending tasks itself.
                queue.task_done()
                continue

        if company_id in _busy_companies:
            queue.task_done()
            await asyncio.sleep(_requeue_delay)
            await queue.put(task_id)
            continue

        _busy_companies.add(company_id)
        try:
            new_status = await run_step(task_id)
            if new_status == "delegated":
                pass  # parent re-queue handled by the delegation completion hook (build phase 5)
        except Exception:
            logger.exception("[%s] run_step crashed for task %s", worker_name, task_id)
            async with session_scope() as session:
                task = await session.get(Task, task_id)
                if task and task.status not in ("completed", "failed"):
                    task.status = "failed"
                    task.result = "Internal error — see server log."
        finally:
            _busy_companies.discard(company_id)
            queue.task_done()


async def requeue_pending_on_startup() -> None:
    async with session_scope() as session:
        rows = (
            await session.execute(select(Task).where(Task.status.in_(["pending", "in_progress"])))
        ).scalars().all()
        for task in rows:
            if task.status == "in_progress":
                task.status = "pending"
    for task in rows:
        await enqueue_task(task.id)
    if rows:
        logger.info("Requeued %d pending/in_progress tasks on startup", len(rows))


def start_workers() -> None:
    for i in range(WORKER_CONCURRENCY):
        _worker_tasks.append(asyncio.create_task(_worker_loop(f"worker-{i}")))


async def stop_workers() -> None:
    for t in _worker_tasks:
        t.cancel()
    for t in _worker_tasks:
        try:
            await t
        except asyncio.CancelledError:
            pass
    _worker_tasks.clear()
