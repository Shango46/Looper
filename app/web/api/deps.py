from fastapi import Header, HTTPException

from app.db.session import session_scope
from app.remote.auth import get_company_for_token


async def get_authenticated_company_id(authorization: str | None = Header(default=None)) -> int:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, detail={"error": "invalid_token"})
    token = authorization.split(" ", 1)[1].strip()

    async with session_scope() as session:
        company, error = await get_company_for_token(session, token)
        if error:
            raise HTTPException(401, detail={"error": error})
        return company.id
