from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.agents.chat import ACTIVE_STATUSES, ChatAgentFiredError, ChatBusyError, latest_chat_task, send_message
from app.db.models import Agent
from app.db.session import session_scope
from app.web.templates_env import templates

router = APIRouter()


@router.get("/agents/{agent_id}/chat")
async def chat_view(request: Request, agent_id: int):
    async with session_scope() as session:
        agent = await session.get(Agent, agent_id)
        if not agent:
            raise HTTPException(404, "Agent not found")
        task = await latest_chat_task(session, agent_id)
    busy = bool(task and task.status in ACTIVE_STATUSES)
    return templates.TemplateResponse(
        "agent_chat.html",
        {"request": request, "agent": agent, "task": task, "busy": busy},
    )


@router.post("/agents/{agent_id}/chat")
async def send_chat_message(agent_id: int, message: str = Form(...)):
    async with session_scope() as session:
        agent = await session.get(Agent, agent_id)
        if not agent:
            raise HTTPException(404, "Agent not found")
        try:
            task_id = await send_message(session, agent, message)
        except ChatAgentFiredError as e:
            raise HTTPException(400, str(e))
        except ChatBusyError as e:
            raise HTTPException(409, str(e))

    from app.worker import enqueue_task

    await enqueue_task(task_id)
    return RedirectResponse(f"/agents/{agent_id}/chat", status_code=303)
