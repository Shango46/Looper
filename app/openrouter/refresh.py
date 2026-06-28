import datetime as dt

from sqlalchemy import delete

from app.db.models import CachedModel
from app.db.session import session_scope
from app.openrouter.client import list_models, model_supports_tools


async def refresh_cached_models() -> int:
    """Fetches the live OpenRouter catalog and replaces the local cache. Returns model count."""
    raw_models = await list_models()
    now = dt.datetime.now(dt.timezone.utc)

    async with session_scope() as session:
        await session.execute(delete(CachedModel))
        for m in raw_models:
            pricing = m.get("pricing") or {}
            arch = m.get("architecture") or {}
            session.add(
                CachedModel(
                    id=m["id"],
                    name=m.get("name") or m["id"],
                    context_length=m.get("context_length"),
                    supports_tools=model_supports_tools(m),
                    pricing_prompt=str(pricing.get("prompt")) if pricing.get("prompt") is not None else None,
                    pricing_completion=str(pricing.get("completion")) if pricing.get("completion") is not None else None,
                    modality=arch.get("modality"),
                    refreshed_at=now,
                )
            )
    return len(raw_models)
