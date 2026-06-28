import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.agents.paths import is_inside_folder, resolve_path
from app.db.models import Company
from app.db.session import session_scope
from app.web.api.deps import get_authenticated_company_id

router = APIRouter()


class CopyMoveRequest(BaseModel):
    src: str
    dst: str


class DeleteRequest(BaseModel):
    path: str


async def _get_company_folder(company_id: int) -> str:
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")
        return company.folder_path


def _safe_resolve(company_folder: str, relative_path: str) -> Path:
    try:
        resolved = resolve_path(company_folder, relative_path)
    except Exception:
        raise HTTPException(400, f"Could not resolve path '{relative_path}'")
    if not is_inside_folder(company_folder, resolved):
        raise HTTPException(400, f"Path '{relative_path}' resolves outside the company folder.")
    return resolved


@router.get("/files")
async def list_files(path: str = ".", company_id: int = Depends(get_authenticated_company_id)):
    company_folder = await _get_company_folder(company_id)
    target = _safe_resolve(company_folder, path)
    if not target.exists():
        raise HTTPException(404, f"'{path}' does not exist.")
    if target.is_file():
        st = target.stat()
        return [{"name": target.name, "is_dir": False, "size": st.st_size, "modified": st.st_mtime}]
    entries = []
    for e in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        st = e.stat()
        entries.append({"name": e.name, "is_dir": e.is_dir(), "size": st.st_size if e.is_file() else 0, "modified": st.st_mtime})
    return entries


@router.post("/files/copy")
async def copy_file(body: CopyMoveRequest, company_id: int = Depends(get_authenticated_company_id)):
    company_folder = await _get_company_folder(company_id)
    src = _safe_resolve(company_folder, body.src)
    dst = _safe_resolve(company_folder, body.dst)
    if not src.exists():
        raise HTTPException(404, f"'{body.src}' does not exist.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)
    return {"ok": True}


@router.post("/files/move")
async def move_file(body: CopyMoveRequest, company_id: int = Depends(get_authenticated_company_id)):
    company_folder = await _get_company_folder(company_id)
    src = _safe_resolve(company_folder, body.src)
    dst = _safe_resolve(company_folder, body.dst)
    if not src.exists():
        raise HTTPException(404, f"'{body.src}' does not exist.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return {"ok": True}


@router.post("/files/delete")
async def delete_file(body: DeleteRequest, company_id: int = Depends(get_authenticated_company_id)):
    company_folder = await _get_company_folder(company_id)
    target = _safe_resolve(company_folder, body.path)
    if not target.exists():
        raise HTTPException(404, f"'{body.path}' does not exist.")
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    return {"ok": True}


@router.get("/files/download")
async def download_file(path: str, company_id: int = Depends(get_authenticated_company_id)):
    company_folder = await _get_company_folder(company_id)
    target = _safe_resolve(company_folder, path)
    if not target.exists() or not target.is_file():
        raise HTTPException(404, f"'{path}' does not exist or is not a file.")
    return FileResponse(target, filename=target.name)


@router.post("/files/upload")
async def upload_file(path: str, file: UploadFile, company_id: int = Depends(get_authenticated_company_id)):
    company_folder = await _get_company_folder(company_id)
    target_dir = _safe_resolve(company_folder, path)
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_filename = Path(file.filename or "upload").name  # strip any directory components a client might send
    target = _safe_resolve(company_folder, f"{path.rstrip('/')}/{safe_filename}")
    contents = await file.read()
    target.write_bytes(contents)
    return {"ok": True, "path": str(target.relative_to(company_folder))}
