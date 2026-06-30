import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from app.agents.paths import is_inside_folder, resolve_path
from app.db.models import Company
from app.db.session import session_scope
from app.web.templates_env import templates

router = APIRouter()

TEXT_EXTENSIONS = {
    ".txt", ".md", ".json", ".yaml", ".yml", ".toml", ".py", ".js", ".ts",
    ".jsx", ".tsx", ".html", ".css", ".sh", ".bat", ".csv", ".log", ".env",
    ".ini", ".cfg", ".xml", ".sql", ".rs", ".go", ".rb", ".java", ".c", ".cpp", ".h",
}


async def _get_company(company_id: int) -> Company:
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")
        return company


def _safe_resolve(company_folder: str, relative_path: str) -> Path:
    try:
        resolved = resolve_path(company_folder, relative_path)
    except Exception:
        raise HTTPException(400, "Invalid path")
    if not is_inside_folder(company_folder, resolved):
        raise HTTPException(400, "Path resolves outside the company folder")
    return resolved


def _humanize_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size} {unit}"
        size //= 1024
    return f"{size} TB"


def _list_dir(target: Path, base: Path) -> list[dict]:
    entries = []
    for e in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        st = e.stat()
        rel = str(e.relative_to(base)).replace("\\", "/")
        entries.append({
            "name": e.name,
            "rel": rel,
            "is_dir": e.is_dir(),
            "size": _humanize_size(st.st_size) if e.is_file() else "",
            "modified": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "is_text": e.is_file() and e.suffix.lower() in TEXT_EXTENSIONS,
        })
    return entries


def _crumbs(rel: str) -> list[dict]:
    crumbs = [{"label": "root", "path": "."}]
    if rel in (".", ""):
        return crumbs
    accumulated = ""
    for part in Path(rel).parts:
        accumulated = f"{accumulated}/{part}".lstrip("/")
        crumbs.append({"label": part, "path": accumulated})
    return crumbs


def _rel(target: Path, base: Path) -> str:
    if target == base:
        return "."
    return str(target.relative_to(base)).replace("\\", "/")


def _listing_ctx(company: Company, target: Path) -> dict:
    base = Path(company.folder_path)
    rel = _rel(target, base)
    return {
        "company": company,
        "path": rel,
        "crumbs": _crumbs(rel),
        "entries": _list_dir(target, base),
    }


@router.get("/companies/{company_id}/files")
async def files_page(request: Request, company_id: int, path: str = "."):
    company = await _get_company(company_id)
    base = Path(company.folder_path)
    target = _safe_resolve(company.folder_path, path)
    if not target.exists() or not target.is_dir():
        target = base
    ctx = _listing_ctx(company, target)
    ctx["request"] = request
    return templates.TemplateResponse("company_files.html", ctx)


@router.get("/companies/{company_id}/files/browse")
async def files_browse(request: Request, company_id: int, path: str = "."):
    company = await _get_company(company_id)
    target = _safe_resolve(company.folder_path, path)
    if not target.exists() or not target.is_dir():
        raise HTTPException(404, "Directory not found")
    ctx = _listing_ctx(company, target)
    ctx["request"] = request
    return templates.TemplateResponse("_file_listing.html", ctx)


@router.get("/companies/{company_id}/files/read")
async def files_read(request: Request, company_id: int, path: str):
    company = await _get_company(company_id)
    target = _safe_resolve(company.folder_path, path)
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "File not found")
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise HTTPException(400, f"Cannot read file: {exc}")
    return templates.TemplateResponse("_file_editor.html", {
        "request": request,
        "company": company,
        "path": path,
        "name": target.name,
        "content": content,
    })


@router.post("/companies/{company_id}/files/write")
async def files_write(company_id: int, path: str = Form(...), content: str = Form(...)):
    company = await _get_company(company_id)
    target = _safe_resolve(company.folder_path, path)
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "File not found")
    target.write_text(content, encoding="utf-8")
    return HTMLResponse('<span class="muted" style="font-size:13px;">&#10003; Saved</span>')


@router.post("/companies/{company_id}/files/mkdir")
async def files_mkdir(request: Request, company_id: int, path: str = Form(...), name: str = Form(...)):
    company = await _get_company(company_id)
    safe_name = Path(name).name
    parent = _safe_resolve(company.folder_path, path)
    new_dir = _safe_resolve(company.folder_path, f"{path.rstrip('/')}/{safe_name}")
    new_dir.mkdir(parents=True, exist_ok=True)
    ctx = _listing_ctx(company, parent)
    ctx["request"] = request
    return templates.TemplateResponse("_file_listing.html", ctx)


@router.post("/companies/{company_id}/files/delete")
async def files_delete(request: Request, company_id: int, path: str = Form(...)):
    company = await _get_company(company_id)
    target = _safe_resolve(company.folder_path, path)
    if not target.exists():
        raise HTTPException(404, "Not found")
    parent = target.parent
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    ctx = _listing_ctx(company, parent)
    ctx["request"] = request
    return templates.TemplateResponse("_file_listing.html", ctx)


@router.post("/companies/{company_id}/files/upload")
async def files_upload(
    request: Request,
    company_id: int,
    path: str = Form(...),
    file: UploadFile = File(...),
):
    company = await _get_company(company_id)
    target_dir = _safe_resolve(company.folder_path, path)
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "upload").name
    dest = _safe_resolve(company.folder_path, f"{path.rstrip('/')}/{safe_name}")
    dest.write_bytes(await file.read())
    ctx = _listing_ctx(company, target_dir)
    ctx["request"] = request
    return templates.TemplateResponse("_file_listing.html", ctx)


@router.get("/companies/{company_id}/files/download")
async def files_download(company_id: int, path: str):
    company = await _get_company(company_id)
    target = _safe_resolve(company.folder_path, path)
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(target, filename=target.name)
