import datetime as dt
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.agents.lifecycle import LifecycleError
from app.agents.lifecycle import create_task_for_ceo as create_task_for_ceo_lifecycle
from app.agents.lifecycle import hire_agent as hire_agent_lifecycle
from app.config import MAX_COMPANIES
from app.crypto import encrypt
from app.db.models import Agent, AgentExtraManager, AgentTemplate, CachedModel, Company, McpServer, Settings, Task, WebSearchRecord
from app.db.session import session_scope
from app.remote.auth import disable_remote_access, generate_code, rotate_code
from app.remote.tailscale import get_tailscale_ip
from app.web.org_tree import build_mermaid_chart, build_org_tree
from app.web.templates_env import templates

router = APIRouter()


async def _cached_models():
    async with session_scope() as session:
        rows = (await session.execute(select(CachedModel).order_by(CachedModel.supports_tools.desc(), CachedModel.name))).scalars().all()
        return rows


@router.get("/")
async def dashboard(request: Request):
    async with session_scope() as session:
        companies = (
            await session.execute(select(Company).options(selectinload(Company.agents)))
        ).scalars().all()
        for c in companies:
            c.ceo = next((a for a in c.agents if a.parent_agent_id is None and a.status != "fired"), None)
        models = await _cached_models()
        agent_templates = (
            await session.execute(select(AgentTemplate).order_by(AgentTemplate.name))
        ).scalars().all()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "companies": companies, "max_companies": MAX_COMPANIES, "models": models, "agent_templates": agent_templates},
    )


@router.post("/companies")
async def create_company(
    name: str = Form(...),
    folder_path: str = Form(...),
    openrouter_api_key: str = Form(...),
    ceo_name: str = Form(...),
    ceo_title: str = Form(...),
    ceo_personality: str = Form(""),
    ceo_model_id: str = Form(...),
):
    async with session_scope() as session:
        count = (await session.execute(select(Company))).scalars().all()
        if len(count) >= MAX_COMPANIES:
            raise HTTPException(400, f"Maximum of {MAX_COMPANIES} companies reached.")

        resolved = Path(folder_path).expanduser().resolve()
        resolved.mkdir(parents=True, exist_ok=True)

        company = Company(
            name=name,
            folder_path=str(resolved),
            openrouter_api_key_encrypted=encrypt(openrouter_api_key),
        )
        session.add(company)
        await session.flush()

        ceo = Agent(
            company_id=company.id,
            parent_agent_id=None,
            name=ceo_name,
            title=ceo_title,
            personality=ceo_personality,
            model_id=ceo_model_id,
            status="active",
        )
        session.add(ceo)
        company_id = company.id

    return RedirectResponse(f"/companies/{company_id}", status_code=303)


@router.get("/companies/{company_id}")
async def company_detail(request: Request, company_id: int):
    async with session_scope() as session:
        company = await session.get(Company, company_id, options=[selectinload(Company.agents)])
        if not company:
            raise HTTPException(404, "Company not found")
        all_agents = company.agents
        tree = build_org_tree(all_agents)
        models = await _cached_models()
        agent_templates = (
            await session.execute(select(AgentTemplate).order_by(AgentTemplate.name))
        ).scalars().all()
    return templates.TemplateResponse(
        "company_detail.html",
        {
            "request": request,
            "company": company,
            "tree": tree,
            "all_agents": all_agents,
            "models": models,
            "agent_templates": agent_templates,
        },
    )


@router.post("/companies/{company_id}/pause")
async def pause_company(company_id: int):
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")
        company.paused = True
    return RedirectResponse(f"/companies/{company_id}", status_code=303)


@router.post("/companies/{company_id}/resume")
async def resume_company(company_id: int):
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")
        company.paused = False
        pending_tasks = (
            await session.execute(select(Task.id).where(Task.company_id == company_id, Task.status == "pending"))
        ).scalars().all()

    from app.worker import enqueue_task

    for tid in pending_tasks:
        await enqueue_task(tid)

    return RedirectResponse(f"/companies/{company_id}", status_code=303)


@router.get("/companies/{company_id}/orgchart")
async def company_orgchart(request: Request, company_id: int):
    async with session_scope() as session:
        company = await session.get(
            Company, company_id,
            options=[selectinload(Company.agents).selectinload(Agent.extra_manager_links)]
        )
        if not company:
            raise HTTPException(404, "Company not found")
        mermaid_chart = build_mermaid_chart(company.agents)
    return templates.TemplateResponse(
        "company_orgchart.html",
        {"request": request, "company": company, "mermaid_chart": mermaid_chart},
    )


@router.post("/companies/{company_id}/orgchart/save-png")
async def save_orgchart_png(company_id: int):
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")
        folder = company.folder_path
    try:
        from playwright.async_api import async_playwright
        timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"orgchart_{timestamp}.png"
        filepath = Path(folder) / filename
        Path(folder).mkdir(parents=True, exist_ok=True)
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            # Very large viewport so Mermaid renders the full chart unconstrained
            page = await browser.new_page(viewport={"width": 6000, "height": 4000})
            await page.goto(
                f"http://127.0.0.1:8731/companies/{company_id}/orgchart",
                wait_until="domcontentloaded",
                timeout=15000,
            )
            await page.wait_for_selector(".mermaid svg", timeout=15000)
            await page.wait_for_timeout(1000)
            # Remove overflow clipping so the SVG can expand freely, then measure
            dims = await page.evaluate("""() => {
                const card = document.querySelector('.card');
                if (card) { card.style.overflow = 'visible'; card.style.minHeight = 'unset'; }
                const mermaidDiv = document.querySelector('.mermaid');
                if (mermaidDiv) mermaidDiv.style.overflow = 'visible';
                const svg = document.querySelector('.mermaid svg');
                svg.style.maxWidth = 'none';
                // getBoundingClientRect returns actual CSS pixel dimensions
                const rect = svg.getBoundingClientRect();
                return { width: Math.ceil(rect.width), height: Math.ceil(rect.height) };
            }""")
            w = max(dims["width"] + 60, 400)
            h = max(dims["height"] + 60, 300)
            await page.set_viewport_size({"width": w, "height": h})
            await page.wait_for_timeout(300)
            await page.locator(".mermaid svg").screenshot(path=str(filepath))
            await browser.close()
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    return {"ok": True, "filename": filename}


@router.post("/companies/{company_id}/agents")
async def create_agent(
    request: Request,
    company_id: int,
    parent_agent_id: int = Form(...),
    name: str = Form(...),
    title: str = Form(...),
    personality: str = Form(""),
    model_id: str = Form(...),
):
    form = await request.form()
    extra_ids = [int(v) for v in form.getlist("extra_manager_ids") if str(v).strip()]

    async with session_scope() as session:
        try:
            agent = await hire_agent_lifecycle(session, company_id, parent_agent_id, name, title, personality, model_id)
        except LifecycleError as e:
            raise HTTPException(400, str(e))
        for mid in extra_ids:
            if mid != parent_agent_id:
                session.add(AgentExtraManager(agent_id=agent.id, manager_id=mid))

    return RedirectResponse(f"/companies/{company_id}", status_code=303)


@router.post("/companies/{company_id}/instruct")
async def instruct_company(request: Request, company_id: int, instruction: str = Form(...)):
    async with session_scope() as session:
        try:
            task = await create_task_for_ceo_lifecycle(session, company_id, instruction)
        except LifecycleError as e:
            raise HTTPException(400, str(e))
        task_id = task.id

    from app.worker import enqueue_task

    await enqueue_task(task_id)
    note = "Sent to CEO and queued for processing."

    return templates.TemplateResponse(
        "_instruct_result.html", {"request": request, "note": note}
    )


@router.get("/companies/{company_id}/settings")
async def company_settings(request: Request, company_id: int, new_code: str | None = None):
    month_start = dt.datetime.now(dt.timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")
        mcp_servers = (
            await session.execute(select(McpServer).where(McpServer.company_id == company_id))
        ).scalars().all()
        global_settings = await session.get(Settings, 1)
        remote_access_enabled = global_settings.remote_access_enabled if global_settings else False

        brave_monthly_total = (await session.execute(
            select(func.count(WebSearchRecord.id)).where(
                WebSearchRecord.company_id == company_id,
                WebSearchRecord.created_at >= month_start,
            )
        )).scalar_one()

        brave_agent_stats = (await session.execute(
            select(Agent.name, func.count(WebSearchRecord.id).label("cnt"))
            .join(Agent, Agent.id == WebSearchRecord.agent_id)
            .where(
                WebSearchRecord.company_id == company_id,
                WebSearchRecord.created_at >= month_start,
            )
            .group_by(Agent.id, Agent.name)
            .order_by(func.count(WebSearchRecord.id).desc())
            .limit(10)
        )).all()

    tailscale_ip = get_tailscale_ip() if remote_access_enabled else None
    return templates.TemplateResponse(
        "company_settings.html",
        {
            "request": request,
            "company": company,
            "new_code": new_code,
            "tailscale_ip": tailscale_ip,
            "mcp_servers": mcp_servers,
            "remote_access_enabled": remote_access_enabled,
            "brave_monthly_total": brave_monthly_total,
            "brave_agent_stats": brave_agent_stats,
            "brave_month": month_start.strftime("%B %Y"),
        },
    )


@router.post("/companies/{company_id}/remote-code/generate")
async def generate_remote_code(company_id: int):
    code = generate_code()
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")
        await rotate_code(session, company, code)
    return RedirectResponse(f"/companies/{company_id}/settings?new_code={code}", status_code=303)


@router.post("/companies/{company_id}/remote-code")
async def set_remote_code(company_id: int, code: str = Form(...)):
    normalized = code.strip().upper()
    if len(normalized) != 8 or not normalized.isalnum():
        raise HTTPException(400, "Code must be exactly 8 letters/numbers.")
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")
        await rotate_code(session, company, normalized)
    return RedirectResponse(f"/companies/{company_id}/settings?new_code={normalized}", status_code=303)


@router.post("/companies/{company_id}/remote-code/disable")
async def disable_remote_code(company_id: int):
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")
        await disable_remote_access(session, company)
    return RedirectResponse(f"/companies/{company_id}/settings", status_code=303)


@router.post("/companies/{company_id}/settings")
async def update_company_settings(
    company_id: int,
    name: str = Form(...),
    folder_path: str = Form(...),
    openrouter_api_key: str = Form(""),
    heartbeats_enabled: bool = Form(False),
    budget_usd_cap: str = Form(""),
):
    new_name = name.strip()
    try:
        resolved = Path(folder_path).expanduser().resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        resolved_path = str(resolved)
    except OSError:
        resolved_path = None
    try:
        budget = float(budget_usd_cap) if budget_usd_cap.strip() else None
    except ValueError:
        budget = None

    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")
        if new_name:
            company.name = new_name
        if resolved_path is not None:
            company.folder_path = resolved_path
        company.heartbeats_enabled = heartbeats_enabled
        company.budget_usd_cap = budget
        if openrouter_api_key.strip():
            company.openrouter_api_key_encrypted = encrypt(openrouter_api_key.strip())
    return RedirectResponse(f"/companies/{company_id}/settings", status_code=303)


@router.post("/companies/{company_id}/reset-spend")
async def reset_spend(company_id: int):
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")
        company.spend_usd_total = 0.0
    return RedirectResponse(f"/companies/{company_id}/settings", status_code=303)


@router.get("/companies/{company_id}/tasks")
async def company_tasks(request: Request, company_id: int):
    async with session_scope() as session:
        company = await session.get(Company, company_id, options=[selectinload(Company.agents)])
        if not company:
            raise HTTPException(404, "Company not found")
        agent_names = {a.id: a.name for a in company.agents}
        tasks = (
            await session.execute(
                select(Task).where(Task.company_id == company_id).order_by(Task.id.desc()).limit(100)
            )
        ).scalars().all()
    return templates.TemplateResponse(
        "company_tasks.html",
        {"request": request, "company": company, "tasks": tasks, "agent_names": agent_names},
    )


# ── Email settings ────────────────────────────────────────────────────────────

@router.post("/companies/{company_id}/email/settings")
async def save_email_settings(
    company_id: int,
    email_display_name: str = Form(""),
    email_smtp_host: str = Form(""),
    email_smtp_port: str = Form(""),
    email_smtp_username: str = Form(""),
    email_smtp_password: str = Form(""),
    email_smtp_use_tls: bool = Form(False),
    email_imap_host: str = Form(""),
    email_imap_port: str = Form(""),
    email_imap_username: str = Form(""),
    email_imap_password: str = Form(""),
    email_imap_use_ssl: bool = Form(False),
):
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")

        company.email_display_name = email_display_name.strip() or None
        company.email_smtp_host = email_smtp_host.strip() or None
        company.email_smtp_port = int(email_smtp_port) if email_smtp_port.strip().isdigit() else None
        company.email_smtp_username = email_smtp_username.strip() or None
        company.email_smtp_use_tls = email_smtp_use_tls
        if email_smtp_password.strip():
            company.email_smtp_password_encrypted = encrypt(email_smtp_password.strip())

        company.email_imap_host = email_imap_host.strip() or None
        company.email_imap_port = int(email_imap_port) if email_imap_port.strip().isdigit() else None
        company.email_imap_username = email_imap_username.strip() or None
        company.email_imap_use_ssl = email_imap_use_ssl
        if email_imap_password.strip():
            company.email_imap_password_encrypted = encrypt(email_imap_password.strip())

    return RedirectResponse(f"/companies/{company_id}/settings", status_code=303)


@router.post("/companies/{company_id}/email/test-smtp")
async def test_smtp_connection(
    company_id: int,
    email_smtp_host: str = Form(""),
    email_smtp_port: str = Form(""),
    email_smtp_username: str = Form(""),
    email_smtp_password: str = Form(""),
    email_smtp_use_tls: bool = Form(False),
):
    from app.email_client import test_smtp

    class _FakeCompany:
        pass

    c = _FakeCompany()
    c.email_smtp_host = email_smtp_host.strip() or None
    c.email_smtp_port = int(email_smtp_port) if email_smtp_port.strip().isdigit() else 587
    c.email_smtp_username = email_smtp_username.strip() or None
    c.email_smtp_use_tls = email_smtp_use_tls
    c.email_smtp_password_encrypted = None

    # If a password was provided in the form, use it directly (not yet saved/encrypted)
    _raw_pw = email_smtp_password.strip()

    def _override_smtp_password(_company):
        return _raw_pw

    import app.email_client as _ec
    _orig = _ec._smtp_password
    _ec._smtp_password = _override_smtp_password
    try:
        ok, msg = test_smtp(c)
    finally:
        _ec._smtp_password = _orig

    return JSONResponse({"ok": ok, "message": msg})


@router.post("/companies/{company_id}/email/test-imap")
async def test_imap_connection(
    company_id: int,
    email_imap_host: str = Form(""),
    email_imap_port: str = Form(""),
    email_imap_username: str = Form(""),
    email_imap_password: str = Form(""),
    email_imap_use_ssl: bool = Form(False),
):
    from app.email_client import test_imap

    class _FakeCompany:
        pass

    c = _FakeCompany()
    c.email_imap_host = email_imap_host.strip() or None
    c.email_imap_port = int(email_imap_port) if email_imap_port.strip().isdigit() else 993
    c.email_imap_username = email_imap_username.strip() or None
    c.email_imap_use_ssl = email_imap_use_ssl
    c.email_imap_password_encrypted = None

    _raw_pw = email_imap_password.strip()

    def _override_imap_password(_company):
        return _raw_pw

    import app.email_client as _ec
    _orig = _ec._imap_password
    _ec._imap_password = _override_imap_password
    try:
        ok, msg = test_imap(c)
    finally:
        _ec._imap_password = _orig

    return JSONResponse({"ok": ok, "message": msg})


# ── Brave Search settings ─────────────────────────────────────────────────────

@router.post("/companies/{company_id}/brave/settings")
async def save_brave_settings(
    company_id: int,
    brave_api_key: str = Form(""),
):
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")
        if brave_api_key.strip():
            company.brave_api_key_encrypted = encrypt(brave_api_key.strip())
    return RedirectResponse(f"/companies/{company_id}/settings#brave", status_code=303)


@router.post("/companies/{company_id}/brave/revoke")
async def revoke_brave_key(company_id: int):
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")
        company.brave_api_key_encrypted = None
    return RedirectResponse(f"/companies/{company_id}/settings#brave", status_code=303)
