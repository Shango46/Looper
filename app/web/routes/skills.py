import json

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import Agent, Company, Skill, SkillGrant
from app.db.session import session_scope
from app.skills.export import create_skill_for_agent, from_export_dict, grant_owner_access, to_export_dict
from app.web.templates_env import templates

router = APIRouter()


@router.get("/skills/shop")
async def skill_shop(request: Request):
    async with session_scope() as session:
        shop_skills = (
            await session.execute(select(Skill).where(Skill.visibility == "shop").order_by(Skill.name))
        ).scalars().all()
        companies = (
            await session.execute(select(Company).options(selectinload(Company.agents)))
        ).scalars().all()
        agent_options = [
            (a.id, f"{c.name} / {a.name}") for c in companies for a in c.agents if a.status != "fired"
        ]
    return templates.TemplateResponse(
        "skill_shop.html",
        {"request": request, "skills": shop_skills, "agent_options": agent_options},
    )


@router.post("/skills/shop/new")
async def create_shop_skill(
    name: str = Form(...),
    description: str = Form(""),
    instructions_md: str = Form(""),
    custom_tool_source: str = Form(""),
    custom_tool_schema_json: str = Form(""),
):
    async with session_scope() as session:
        schema = None
        if custom_tool_schema_json.strip():
            try:
                schema = json.loads(custom_tool_schema_json)
            except json.JSONDecodeError:
                raise HTTPException(400, "Custom tool schema must be valid JSON")
        session.add(Skill(
            name=name,
            description=description,
            instructions_md=instructions_md,
            custom_tool_source=custom_tool_source or None,
            custom_tool_schema_json=schema,
            visibility="shop",
            company_id=None,
            owner_agent_id=None,
        ))
    return RedirectResponse("/skills/shop", status_code=303)


@router.post("/skills/{skill_id}/grant")
async def grant_skill(skill_id: int, agent_id: int = Form(...), redirect_to: str = Form("/skills/shop")):
    import datetime as dt

    if not redirect_to.startswith("/"):
        redirect_to = "/skills/shop"

    async with session_scope() as session:
        skill = await session.get(Skill, skill_id)
        if not skill:
            raise HTTPException(404, "Skill not found")
        existing = (
            await session.execute(
                select(SkillGrant).where(SkillGrant.skill_id == skill_id, SkillGrant.agent_id == agent_id)
            )
        ).scalars().first()
        if existing:
            existing.status = "approved"
            existing.resolved_at = dt.datetime.now(dt.timezone.utc)
        else:
            session.add(
                SkillGrant(
                    skill_id=skill_id, agent_id=agent_id, status="approved",
                    resolved_at=dt.datetime.now(dt.timezone.utc)
                )
            )
    return RedirectResponse(redirect_to, status_code=303)


@router.post("/skills/{skill_id}/edit")
async def edit_skill(
    skill_id: int,
    name: str = Form(...),
    description: str = Form(""),
    instructions_md: str = Form(""),
    custom_tool_source: str = Form(""),
    custom_tool_schema_json: str = Form(""),
):
    async with session_scope() as session:
        skill = await session.get(Skill, skill_id)
        if not skill:
            raise HTTPException(404, "Skill not found")
        schema = None
        if custom_tool_schema_json.strip():
            try:
                schema = json.loads(custom_tool_schema_json)
            except json.JSONDecodeError:
                raise HTTPException(400, "Custom tool schema must be valid JSON")
        skill.name = name
        skill.description = description
        skill.instructions_md = instructions_md
        skill.custom_tool_source = custom_tool_source or None
        skill.custom_tool_schema_json = schema
    return RedirectResponse("/skills/shop", status_code=303)


@router.post("/skills/{skill_id}/delete")
async def delete_skill(skill_id: int):
    async with session_scope() as session:
        skill = await session.get(Skill, skill_id)
        if not skill:
            raise HTTPException(404, "Skill not found")
        await session.delete(skill)
    return RedirectResponse("/skills/shop", status_code=303)


@router.post("/skill-grants/{grant_id}/revoke")
async def revoke_grant(grant_id: int):
    async with session_scope() as session:
        grant = await session.get(SkillGrant, grant_id)
        if not grant:
            raise HTTPException(404, "Grant not found")
        grant.status = "revoked"
        agent_id = grant.agent_id
    return RedirectResponse(f"/agents/{agent_id}", status_code=303)


@router.post("/agents/{agent_id}/skills")
async def create_skill(
    agent_id: int,
    name: str = Form(...),
    description: str = Form(""),
    instructions_md: str = Form(""),
    custom_tool_source: str = Form(""),
    custom_tool_schema_json: str = Form(""),
    visibility: str = Form("private"),
):
    async with session_scope() as session:
        agent = await session.get(Agent, agent_id)
        if not agent:
            raise HTTPException(404, "Agent not found")
        schema = None
        if custom_tool_schema_json.strip():
            try:
                schema = json.loads(custom_tool_schema_json)
            except json.JSONDecodeError:
                raise HTTPException(400, "Custom tool schema must be valid JSON")
        await create_skill_for_agent(
            session, agent, name, description, instructions_md, custom_tool_source, schema, visibility
        )
    return RedirectResponse(f"/agents/{agent_id}", status_code=303)


@router.get("/skills/{skill_id}/export")
async def export_skill(skill_id: int):
    async with session_scope() as session:
        skill = await session.get(Skill, skill_id)
        if not skill:
            raise HTTPException(404, "Skill not found")
        data = to_export_dict(skill)
    filename = f"{skill.name.replace(' ', '_')}.skill.json"
    return Response(
        content=json.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/agents/{agent_id}/skills/import")
async def import_skill(agent_id: int, file: UploadFile, visibility: str = Form("private")):
    raw = await file.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(400, "Not a valid .skill.json file")

    async with session_scope() as session:
        agent = await session.get(Agent, agent_id)
        if not agent:
            raise HTTPException(404, "Agent not found")
        kwargs = from_export_dict(data)
        await create_skill_for_agent(session, agent, visibility=visibility, **kwargs)
    return RedirectResponse(f"/agents/{agent_id}", status_code=303)
