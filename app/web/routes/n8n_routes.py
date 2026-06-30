from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select

from app.crypto import encrypt
from app.db.models import Company, N8nTemplate
from app.db.session import session_scope
from app.n8n import client as n8n_client
from app.n8n.process import is_running
from app.web.templates_env import templates

router = APIRouter()


# ── Company n8n page ──────────────────────────────────────────────────────────

@router.get("/companies/{company_id}/n8n")
async def company_n8n_page(request: Request, company_id: int):
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")
        tmpl_rows = (await session.execute(select(N8nTemplate).order_by(N8nTemplate.name))).scalars().all()

    workflows: list[dict] = []
    api_key_ok = bool(n8n_client.load_api_key()) or company.n8n_mode == "cloud"
    if api_key_ok:
        workflows = await n8n_client.list_workflows(company)

    creds = n8n_client.get_credentials() if company.n8n_mode == "self_hosted" else None

    return templates.TemplateResponse("company_n8n.html", {
        "request": request,
        "company": company,
        "workflows": workflows,
        "templates": tmpl_rows,
        "n8n_running": is_running() if company.n8n_mode == "self_hosted" else True,
        "api_key_ok": api_key_ok,
        "ui_url": n8n_client.project_ui_url(company),
        "n8n_email": creds[0] if creds else None,
        "n8n_password": creds[1] if creds else None,
    })


# ── Ensure project exists then open n8n ──────────────────────────────────────

@router.post("/companies/{company_id}/n8n/open")
async def n8n_open(company_id: int):
    """Ensure an n8n project exists for this company, then redirect to n8n UI."""
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")

        if not company.n8n_project_id:
            project_id = await n8n_client.create_project(company)
            if project_id:
                company.n8n_project_id = project_id

        ui_url = n8n_client.project_ui_url(company)

    return RedirectResponse(ui_url, status_code=303)


# ── Workflow list partial (HTMX refresh) ──────────────────────────────────────

@router.get("/companies/{company_id}/n8n/workflows")
async def n8n_workflows_partial(request: Request, company_id: int):
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")

    workflows = await n8n_client.list_workflows(company) if company.n8n_project_id else []
    return templates.TemplateResponse("_n8n_workflows.html", {
        "request": request,
        "company": company,
        "workflows": workflows,
    })


# ── Create workflow from template ─────────────────────────────────────────────

@router.post("/companies/{company_id}/n8n/workflow/from-template/{template_id}")
async def create_from_template(company_id: int, template_id: int):
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        tmpl = await session.get(N8nTemplate, template_id)
        if not company or not tmpl:
            raise HTTPException(404, "Not found")

        if not company.n8n_project_id:
            project_id = await n8n_client.create_project(company)
            if project_id:
                company.n8n_project_id = project_id
            else:
                raise HTTPException(503, "n8n project could not be created")

    result = await n8n_client.create_workflow_from_json(company, tmpl.workflow_json)
    if not result:
        raise HTTPException(503, "Failed to create workflow in n8n")

    return RedirectResponse(f"/companies/{company_id}/n8n", status_code=303)


# ── Save workflow as template ─────────────────────────────────────────────────

@router.post("/companies/{company_id}/n8n/workflow/{workflow_id}/save-template")
async def save_as_template(
    company_id: int,
    workflow_id: str,
    name: str = Form(...),
    description: str = Form(""),
):
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")

    wf_json = await n8n_client.export_workflow(company, workflow_id)
    if not wf_json:
        raise HTTPException(503, "Could not export workflow from n8n")

    async with session_scope() as session:
        tmpl = N8nTemplate(name=name, description=description, workflow_json=wf_json)
        session.add(tmpl)

    return RedirectResponse(f"/companies/{company_id}/n8n", status_code=303)


# ── Template management ───────────────────────────────────────────────────────

@router.post("/n8n/templates/{template_id}/delete")
async def delete_template(template_id: int, company_id: int = Form(...)):
    async with session_scope() as session:
        tmpl = await session.get(N8nTemplate, template_id)
        if tmpl:
            await session.delete(tmpl)
    return RedirectResponse(f"/companies/{company_id}/n8n", status_code=303)


# ── n8n settings (saved from company settings page) ──────────────────────────

@router.post("/companies/{company_id}/n8n/settings")
async def save_n8n_settings(
    company_id: int,
    n8n_mode: str = Form("self_hosted"),
    n8n_cloud_url: str = Form(""),
    n8n_cloud_api_key: str = Form(""),
):
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")
        company.n8n_mode = n8n_mode if n8n_mode in ("self_hosted", "cloud") else "self_hosted"
        if n8n_mode == "cloud":
            company.n8n_cloud_url = n8n_cloud_url.strip() or None
            if n8n_cloud_api_key.strip():
                company.n8n_cloud_api_key_encrypted = encrypt(n8n_cloud_api_key.strip())
        else:
            # Switching back to self-hosted — preserve cloud creds in case they switch back
            pass

    return RedirectResponse(f"/companies/{company_id}/settings", status_code=303)


# ── Test cloud connection ─────────────────────────────────────────────────────

@router.post("/companies/{company_id}/n8n/test-connection")
async def test_connection(
    company_id: int,
    n8n_cloud_url: str = Form(...),
    n8n_cloud_api_key: str = Form(...),
):
    ok = await n8n_client.test_connection(n8n_cloud_url.strip(), n8n_cloud_api_key.strip())
    return JSONResponse({"ok": ok})
