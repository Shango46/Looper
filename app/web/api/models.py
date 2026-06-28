from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.db.models import CachedModel
from app.db.session import session_scope
from app.web.api.deps import get_authenticated_company_id

router = APIRouter()


@router.get("/models")
async def list_models(company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        rows = (
            await session.execute(select(CachedModel).order_by(CachedModel.supports_tools.desc(), CachedModel.name))
        ).scalars().all()
        return [
            {
                "id": m.id,
                "name": m.name,
                "supports_tools": m.supports_tools,
                "context_length": m.context_length,
                "pricing_prompt": m.pricing_prompt,
                "pricing_completion": m.pricing_completion,
                "modality": m.modality,
            }
            for m in rows
        ]
