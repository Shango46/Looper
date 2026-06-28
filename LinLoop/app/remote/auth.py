import datetime as dt
import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Company, RemoteSession

# Unambiguous alphabet — no 0/O, 1/I/L confusion when read off a screen and typed on a phone.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8


def generate_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def normalize_code(code: str) -> str:
    return code.strip().upper()


def hash_code(code: str) -> str:
    return hashlib.sha256(normalize_code(code).encode("utf-8")).hexdigest()


async def find_company_by_code(session: AsyncSession, code: str) -> Company | None:
    """Iterates this PC's own companies (max 10) and hash-compares — codes are only unique
    within a single Looper install, not globally, by design (see plan: Tailscale transport)."""
    target_hash = hash_code(code)
    companies = (await session.execute(select(Company))).scalars().all()
    for company in companies:
        if company.remote_code_hash and company.remote_code_hash == target_hash:
            return company
    return None


async def create_session(session: AsyncSession, company: Company) -> RemoteSession:
    token = secrets.token_urlsafe(32)
    remote_session = RemoteSession(
        company_id=company.id,
        token=token,
        code_version=company.remote_code_version,
    )
    session.add(remote_session)
    await session.flush()
    return remote_session


async def get_company_for_token(session: AsyncSession, token: str) -> tuple[Company | None, str | None]:
    """Returns (company, None) on success, or (None, error_code) where error_code is
    'invalid_token' (unknown/garbage token), 'code_changed' (token was valid but the company's
    code has since been rotated), or 'access_disabled' (remote access was turned off entirely) —
    distinguishable so clients can prompt for re-entry instead of just failing generically.

    Note: rotating/disabling a code deliberately does NOT delete the old RemoteSession row —
    only bumps remote_code_version — so the *next* request on the old token still finds its
    session and can compare versions to produce 'code_changed'/'access_disabled' here, rather
    than the row being gone and falling through to a generic 'invalid_token'."""
    remote_session = (
        await session.execute(select(RemoteSession).where(RemoteSession.token == token))
    ).scalars().first()
    if not remote_session:
        return None, "invalid_token"

    company = await session.get(Company, remote_session.company_id)
    if not company:
        return None, "invalid_token"

    if remote_session.code_version != company.remote_code_version:
        return None, "access_disabled" if not company.remote_code_hash else "code_changed"

    if not company.remote_code_hash:
        return None, "access_disabled"

    remote_session.last_seen_at = dt.datetime.now(dt.timezone.utc)
    return company, None


async def rotate_code(session: AsyncSession, company: Company, new_code: str) -> None:
    """Sets a new code. Deliberately leaves existing RemoteSession rows in place (see
    get_company_for_token) so already-connected clients get a distinguishable 'code_changed'
    on their next request instead of a generic invalid-token failure."""
    company.remote_code_hash = hash_code(new_code)
    company.remote_code_version += 1
    company.remote_code_set_at = dt.datetime.now(dt.timezone.utc)


async def disable_remote_access(session: AsyncSession, company: Company) -> None:
    company.remote_code_hash = None
    company.remote_code_version += 1
    company.remote_code_set_at = None


async def revoke_token(session: AsyncSession, token: str) -> None:
    await session.execute(RemoteSession.__table__.delete().where(RemoteSession.token == token))
