from __future__ import annotations

import asyncio

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse

from app.db.models import Company
from app.db.session import session_scope
from app.rag import store as rag
from app.web.templates_env import templates

router = APIRouter()

_MAX_UPLOAD_MB = 20


@router.get("/companies/{company_id}/rag")
async def rag_page(request: Request, company_id: int, indexed: str = ""):
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")

    docs = await rag.async_list_documents(company_id)
    stats = await rag.async_collection_stats(company_id)
    return templates.TemplateResponse("company_rag.html", {
        "request": request,
        "company": company,
        "docs": docs,
        "stats": stats,
        "indexed": int(indexed) if indexed.isdigit() else 0,
        "supported_ext": sorted(rag.SUPPORTED_EXTENSIONS | {".pdf"}),
    })


@router.post("/companies/{company_id}/rag/upload")
async def rag_upload(company_id: int, file: UploadFile = File(...)):
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")

    content = await file.read()
    if len(content) > _MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {_MAX_UPLOAD_MB} MB limit")

    try:
        result = await rag.async_index_file(company_id, content, file.filename or "upload")
    except ValueError as e:
        raise HTTPException(400, str(e))

    return RedirectResponse(
        f"/companies/{company_id}/rag?indexed={result['chunks_indexed']}", status_code=303
    )


@router.post("/companies/{company_id}/rag/text")
async def rag_index_text(
    company_id: int,
    title: str = Form(...),
    content: str = Form(...),
):
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")

    if not content.strip():
        raise HTTPException(400, "Content cannot be empty")

    result = await rag.async_index_text(
        company_id, content.strip(), title.strip() or "Pasted text"
    )
    return RedirectResponse(
        f"/companies/{company_id}/rag?indexed={result['chunks_indexed']}", status_code=303
    )


@router.get("/companies/{company_id}/rag/documents")
async def rag_documents_partial(request: Request, company_id: int):
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")

    docs = await rag.async_list_documents(company_id)
    stats = await rag.async_collection_stats(company_id)
    return templates.TemplateResponse("_rag_documents.html", {
        "request": request,
        "company": company,
        "docs": docs,
        "stats": stats,
    })


@router.post("/companies/{company_id}/rag/documents/{doc_id}/delete")
async def rag_delete(company_id: int, doc_id: str):
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")

    await asyncio.to_thread(rag.delete_document, company_id, doc_id)
    return RedirectResponse(f"/companies/{company_id}/rag", status_code=303)


@router.post("/companies/{company_id}/rag/search")
async def rag_search(request: Request, company_id: int, query: str = Form(...)):
    async with session_scope() as session:
        company = await session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")

    results = await rag.async_search(company_id, query.strip(), limit=5)
    return templates.TemplateResponse("_rag_search_results.html", {
        "request": request,
        "company": company,
        "query": query,
        "results": results,
    })
