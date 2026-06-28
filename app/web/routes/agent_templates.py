from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.db.models import AgentTemplate, CachedModel
from app.db.session import session_scope
from app.web.templates_env import templates

router = APIRouter()


async def _all_templates(session):
    return (
        await session.execute(select(AgentTemplate).order_by(AgentTemplate.name))
    ).scalars().all()


async def _cached_models(session):
    return (
        await session.execute(
            select(CachedModel).order_by(CachedModel.supports_tools.desc(), CachedModel.name)
        )
    ).scalars().all()


@router.get("/agents/shop")
async def agent_shop(request: Request):
    async with session_scope() as session:
        agent_templates = await _all_templates(session)
        models = await _cached_models(session)
    return templates.TemplateResponse(
        "agent_shop.html",
        {"request": request, "agent_templates": agent_templates, "models": models},
    )


@router.post("/agents/shop")
async def create_agent_template(
    name: str = Form(...),
    title: str = Form(...),
    personality: str = Form(""),
    recommended_model_id: str = Form(""),
):
    async with session_scope() as session:
        session.add(AgentTemplate(
            name=name.strip(),
            title=title.strip(),
            personality=personality.strip(),
            recommended_model_id=recommended_model_id.strip() or None,
        ))
    return RedirectResponse("/agents/shop", status_code=303)


@router.post("/agents/shop/{template_id}/edit")
async def edit_agent_template(
    template_id: int,
    name: str = Form(...),
    title: str = Form(...),
    personality: str = Form(""),
    recommended_model_id: str = Form(""),
):
    async with session_scope() as session:
        tpl = await session.get(AgentTemplate, template_id)
        if not tpl:
            raise HTTPException(404, "Agent template not found")
        tpl.name = name.strip()
        tpl.title = title.strip()
        tpl.personality = personality.strip()
        tpl.recommended_model_id = recommended_model_id.strip() or None
    return RedirectResponse("/agents/shop", status_code=303)


@router.post("/agents/shop/{template_id}/delete")
async def delete_agent_template(template_id: int):
    async with session_scope() as session:
        tpl = await session.get(AgentTemplate, template_id)
        if not tpl:
            raise HTTPException(404, "Agent template not found")
        await session.delete(tpl)
    return RedirectResponse("/agents/shop", status_code=303)
