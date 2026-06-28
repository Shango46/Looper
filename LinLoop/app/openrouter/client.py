import asyncio
import logging

import httpx

from app.config import OPENROUTER_BASE_URL

logger = logging.getLogger("looper.openrouter")

MAX_RETRIES = 3


class OpenRouterError(Exception):
    pass


async def list_models() -> list[dict]:
    """GET /models — public catalog, no auth required. Returns raw model dicts."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{OPENROUTER_BASE_URL}/models")
        resp.raise_for_status()
        return resp.json().get("data", [])


def model_supports_tools(model: dict) -> bool:
    return "tools" in (model.get("supported_parameters") or [])


async def chat_completion(
    api_key: str,
    model: str,
    messages: list[dict],
    tools: list[dict] | None = None,
) -> dict:
    """POST /chat/completions with retry/backoff on 429/5xx. Returns the raw JSON response."""
    payload: dict = {"model": model, "messages": messages}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://127.0.0.1",
        "X-Title": "Looper",
    }

    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions", json=payload, headers=headers
                )
            if resp.status_code == 429 or resp.status_code >= 500:
                wait = 2**attempt
                logger.warning("OpenRouter %s, retrying in %ss", resp.status_code, wait)
                await asyncio.sleep(wait)
                last_exc = OpenRouterError(f"HTTP {resp.status_code}: {resp.text[:500]}")
                continue
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise OpenRouterError(f"HTTP {e.response.status_code}: {e.response.text[:500]}") from e
        except httpx.RequestError as e:
            last_exc = e
            await asyncio.sleep(2**attempt)

    raise OpenRouterError(f"OpenRouter request failed after {MAX_RETRIES} attempts: {last_exc}")
