import datetime as dt
import json
from urllib.parse import quote

from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "web" / "templates"))


def _modality_category(modality: str | None) -> str:
    if not modality:
        return "text"
    parts = modality.split("->")
    inputs = parts[0] if parts else ""
    outputs = parts[1] if len(parts) > 1 else ""
    if "image" in outputs or "video" in outputs:
        return "image"
    if "audio" in outputs and "text" not in outputs:
        return "audio"
    if "video" in inputs:
        return "video"
    if "image" in inputs:
        return "vision"
    if "audio" in inputs and "text" not in inputs:
        return "audio"
    return "text"


def models_to_json(models) -> str:
    """Serialize a list of CachedModel rows to a JSON array safe for embedding in <script> tags.
    json.dumps doesn't escape < > & by default, which breaks HTML parsing mid-script."""
    result = []
    for m in models:
        try:
            pin = round(float(m.pricing_prompt) * 1_000_000, 6) if m.pricing_prompt else 0.0
        except (ValueError, TypeError):
            pin = 0.0
        try:
            pout = round(float(m.pricing_completion) * 1_000_000, 6) if m.pricing_completion else 0.0
        except (ValueError, TypeError):
            pout = 0.0
        result.append({
            "id": m.id,
            "name": m.name,
            "cat": _modality_category(getattr(m, "modality", None)),
            "price_in": pin,
            "price_out": pout,
            "ctx": m.context_length or 0,
            "tools": bool(m.supports_tools),
        })
    raw = json.dumps(result)
    # Escape characters that break HTML parsing inside <script> tags
    return raw.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


templates.env.globals["models_to_json"] = models_to_json


def agent_templates_to_json(agent_templates) -> str:
    result = []
    for t in agent_templates:
        result.append({
            "id": t.id,
            "name": t.name,
            "title": t.title,
            "personality": t.personality,
            "recommended_model_id": t.recommended_model_id or "",
        })
    raw = json.dumps(result)
    return raw.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


templates.env.globals["agent_templates_to_json"] = agent_templates_to_json


def _timeago(value: dt.datetime) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    diff = int((now - value).total_seconds())
    if diff < 5:
        return "just now"
    if diff < 60:
        return f"{diff}s ago"
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    return f"{diff // 86400}d ago"


templates.env.filters["timeago"] = _timeago
templates.env.filters["urlquote"] = lambda s: quote(str(s), safe="/")
