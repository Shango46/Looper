from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from app.db.session import session_scope
from app.remote.auth import create_session, find_company_by_code, revoke_token
from app.remote.ratelimit import check_and_record

router = APIRouter()


class ConnectRequest(BaseModel):
    code: str


@router.post("/connect")
async def connect(body: ConnectRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if not check_and_record(client_ip):
        raise HTTPException(429, detail={"error": "too_many_attempts"})

    async with session_scope() as session:
        company = await find_company_by_code(session, body.code)
        if not company:
            raise HTTPException(401, detail={"error": "invalid_code"})
        remote_session = await create_session(session, company)
        return {"token": remote_session.token, "company_id": company.id, "company_name": company.name}


@router.post("/disconnect")
async def disconnect(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        return {"ok": True}
    token = authorization.split(" ", 1)[1].strip()
    async with session_scope() as session:
        await revoke_token(session, token)
    return {"ok": True}
