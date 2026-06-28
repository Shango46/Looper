from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.db.models import AgentTemplate
from app.db.session import session_scope
from app.web.api.deps import get_authenticated_company_id

router = APIRouter()


@router.get("/agent-templates")
async def list_agent_templates(company_id: int = Depends(get_authenticated_company_id)):
    async with session_scope() as session:
        rows = (
            await session.execute(select(AgentTemplate).order_by(AgentTemplate.name))
        ).scalars().all()
        return [
            {
                "id": t.id,
                "name": t.name,
                "title": t.title,
                "personality": t.personality,
                "recommended_model_id": t.recommended_model_id,
            }
            for t in rows
        ]
