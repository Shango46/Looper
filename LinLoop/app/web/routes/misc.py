from fastapi import APIRouter, Form, Request
from sqlalchemy import select

from app.db.models import CachedModel, Settings
from app.db.session import session_scope
from app.openrouter.refresh import refresh_cached_models
from app.setup.bootstrap import check_environment, run_playwright_install_chromium, run_playwright_install_deps
from app.setup.service import install_service, service_status, uninstall_service
from app.web.templates_env import templates

router = APIRouter()


async def _get_settings_row() -> Settings:
    async with session_scope() as session:
        settings = await session.get(Settings, 1)
        if not settings:
            settings = Settings(id=1)
            session.add(settings)
            await session.flush()
            await session.refresh(settings)
        return settings


@router.get("/settings")
async def global_settings(
    request: Request,
    refreshed: int | None = None,
    error: str | None = None,
    setup_log: str | None = None,
    service_log: str | None = None,
):
    settings = await _get_settings_row()
    async with session_scope() as session:
        models = (
            await session.execute(select(CachedModel).order_by(CachedModel.supports_tools.desc(), CachedModel.name))
        ).scalars().all()
    env = check_environment()
    svc_status = service_status()
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "settings": settings,
            "models": models,
            "refreshed": refreshed,
            "error": error,
            "env": env,
            "setup_log": setup_log,
            "svc_status": svc_status,
            "service_log": service_log,
        },
    )


@router.post("/settings/run-setup")
async def run_setup():
    from fastapi.responses import RedirectResponse

    ok1, log1 = run_playwright_install_chromium()
    ok2, log2 = run_playwright_install_deps()
    combined = f"playwright install chromium: {'OK' if ok1 else 'FAILED'}\n{log1}\n\ninstall-deps: {'OK' if ok2 else 'FAILED'}\n{log2}"
    import urllib.parse

    return RedirectResponse(f"/settings?setup_log={urllib.parse.quote(combined[:1500])}", status_code=303)


@router.post("/settings/refresh-models")
async def refresh_models():
    from fastapi.responses import RedirectResponse

    try:
        count = await refresh_cached_models()
        return RedirectResponse(f"/settings?refreshed={count}", status_code=303)
    except Exception as e:
        return RedirectResponse(f"/settings?error={str(e)[:200]}", status_code=303)


@router.post("/settings/heartbeats-when-closed")
async def toggle_heartbeats_when_closed(enabled: bool = Form(False)):
    import urllib.parse

    from fastapi.responses import RedirectResponse

    if enabled:
        ok, log = install_service()
    else:
        ok, log = uninstall_service()

    async with session_scope() as session:
        settings = await session.get(Settings, 1)
        if not settings:
            settings = Settings(id=1)
            session.add(settings)
        settings.heartbeats_run_when_closed = enabled
        settings.background_service_installed = enabled and ok

    log_msg = f"{'Install' if enabled else 'Uninstall'} {'succeeded' if ok else 'FAILED'}: {log}"
    return RedirectResponse(f"/settings?service_log={urllib.parse.quote(log_msg[:1500])}", status_code=303)
