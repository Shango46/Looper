from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.agents.browser import close_all_browsers
from app.config import BASE_DIR
from app.db.session import init_db
from app.scheduler.heartbeats import start_heartbeat_scheduler, stop_heartbeat_scheduler
from app.web.api import agents as api_agents
from app.web.api import approvals as api_approvals
from app.web.api import auth as api_auth
from app.web.api import files as api_files
from app.web.api import mcp as api_mcp
from app.web.api import me as api_me
from app.web.api import models as api_models
from app.web.api import skills as api_skills
from app.web.api import tasks as api_tasks
from app.web.routes import agents, approvals, chat, companies, heartbeats, mcp, misc, skills, tasks
from app.worker import requeue_pending_on_startup, start_workers, stop_workers


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_workers()
    await requeue_pending_on_startup()
    start_heartbeat_scheduler()
    yield
    await stop_heartbeat_scheduler()
    await stop_workers()
    await close_all_browsers()


app = FastAPI(title="Looper", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "web" / "static")), name="static")

app.include_router(companies.router)
app.include_router(agents.router)
app.include_router(misc.router)
app.include_router(tasks.router)
app.include_router(approvals.router)
app.include_router(heartbeats.router)
app.include_router(skills.router)
app.include_router(chat.router)
app.include_router(mcp.router)

app.include_router(api_auth.router, prefix="/api/v1")
app.include_router(api_me.router, prefix="/api/v1")
app.include_router(api_agents.router, prefix="/api/v1")
app.include_router(api_tasks.router, prefix="/api/v1")
app.include_router(api_approvals.router, prefix="/api/v1")
app.include_router(api_skills.router, prefix="/api/v1")
app.include_router(api_models.router, prefix="/api/v1")
app.include_router(api_mcp.router, prefix="/api/v1")
app.include_router(api_files.router, prefix="/api/v1")
