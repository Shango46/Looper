import urllib.parse

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from app.config import IS_PUBLISHER, get_publisher_token
from app.db.models import CachedModel, Settings
from app.db.session import session_scope
from app.openrouter.refresh import refresh_cached_models
from app.setup.bootstrap import check_environment, run_playwright_install_chromium, run_playwright_install_deps
from app.setup.service import install_service, service_status, uninstall_service
from app.update import apply_update, get_latest_release, get_local_version, has_git, is_newer, next_patch, publish_release, schedule_restart
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
    publish_ok: str | None = None,
    publish_error: str | None = None,
    update_ok: str | None = None,
    update_error: str | None = None,
    restarting: int | None = None,
):
    settings = await _get_settings_row()
    async with session_scope() as session:
        models = (
            await session.execute(select(CachedModel).order_by(CachedModel.supports_tools.desc(), CachedModel.name))
        ).scalars().all()
    env = check_environment()
    svc_status = service_status()
    local_version = get_local_version()
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
            "local_version": local_version,
            "next_version": next_patch(local_version),
            "is_publisher": IS_PUBLISHER,
            "has_git": has_git(),
            "publish_ok": publish_ok,
            "publish_error": publish_error,
            "update_ok": update_ok,
            "update_error": update_error,
            "restarting": restarting,
        },
    )


@router.post("/settings/run-setup")
async def run_setup():
    ok1, log1 = run_playwright_install_chromium()
    ok2, log2 = run_playwright_install_deps()
    combined = f"playwright install chromium: {'OK' if ok1 else 'FAILED'}\n{log1}\n\ninstall-deps: {'OK' if ok2 else 'FAILED'}\n{log2}"
    return RedirectResponse(f"/settings?setup_log={urllib.parse.quote(combined[:1500])}", status_code=303)


@router.post("/settings/refresh-models")
async def refresh_models():
    try:
        count = await refresh_cached_models()
        return RedirectResponse(f"/settings?refreshed={count}", status_code=303)
    except Exception as e:
        return RedirectResponse(f"/settings?error={str(e)[:200]}", status_code=303)


@router.post("/settings/heartbeats-when-closed")
async def toggle_heartbeats_when_closed(enabled: bool = Form(False)):
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


@router.post("/settings/remote-access")
async def toggle_remote_access(enabled: bool = Form(False)):
    async with session_scope() as session:
        settings = await session.get(Settings, 1)
        if not settings:
            settings = Settings(id=1)
            session.add(settings)
        settings.remote_access_enabled = enabled
    return RedirectResponse("/settings", status_code=303)


@router.get("/settings/check-update")
async def check_update(request: Request):
    local = get_local_version()
    release = await get_latest_release()
    if not release:
        return HTMLResponse('<div class="muted" style="margin-top:6px;">Could not reach GitHub — check your internet connection.</div>')
    remote = release.get("tag_name", "").lstrip("v")
    changelog = release.get("body", "")
    if is_newer(remote, local):
        changelog_html = (
            f"<pre class='code' style='max-height:120px;overflow-y:auto;font-size:12px;margin:8px 0;white-space:pre-wrap;'>"
            f"{changelog[:600]}{'…' if len(changelog) > 600 else ''}</pre>"
        ) if changelog else ""
        return HTMLResponse(
            f"<div style='color:var(--ok);font-weight:600;margin-top:6px;'>v{remote} is available!</div>"
            f"{changelog_html}"
            f"<form method='post' action='/settings/update/apply' style='margin-top:6px;'>"
            f"<button type='submit'>Apply Update (git pull + restart)</button>"
            f"</form>"
        )
    return HTMLResponse(f'<div class="muted" style="margin-top:6px;">You are up to date &mdash; latest release is v{remote}.</div>')


@router.post("/settings/publish")
async def publish_release_route(
    version: str = Form(...),
    changelog: str = Form(""),
):
    if not IS_PUBLISHER:
        return RedirectResponse("/settings?publish_error=Not+a+publisher+machine", status_code=303)
    token = get_publisher_token()
    if not token:
        return RedirectResponse("/settings?publish_error=publisher.token+file+is+empty", status_code=303)
    ok, msg = await publish_release(version.strip(), changelog.strip(), token)
    if ok:
        return RedirectResponse(f"/settings?publish_ok={urllib.parse.quote(msg)}", status_code=303)
    return RedirectResponse(f"/settings?publish_error={urllib.parse.quote(msg[:500])}", status_code=303)


@router.post("/settings/update/apply")
async def update_apply():
    ok, msg = await apply_update()
    if ok:
        return RedirectResponse(f"/settings?update_ok={urllib.parse.quote(msg)}", status_code=303)
    return RedirectResponse(f"/settings?update_error={urllib.parse.quote(msg[:500])}", status_code=303)


@router.post("/settings/update/restart")
async def update_restart():
    schedule_restart(1.5)
    return RedirectResponse("/settings?restarting=1", status_code=303)
