"""Company-aware built-in tools.

These tools need access to company-specific config (email credentials, RAG collection)
beyond just the company folder path. They receive a `company_ctx` dict pre-populated
in loop.py from the Company ORM row so no extra DB round-trips are needed at call time.
"""
from __future__ import annotations

import json
import types

RAG_SEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "rag_search",
        "description": (
            "Search this company's knowledge base (uploaded documents, policies, notes) "
            "for information relevant to a query. Use this before searching the web or "
            "asking for information that might be in company documents."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language search query"},
                "limit": {
                    "type": "integer",
                    "description": "Number of results to return (1–10). Default 5.",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
}

EMAIL_SEND_SCHEMA = {
    "type": "function",
    "function": {
        "name": "email_send",
        "description": "Send an email using this company's configured SMTP account.",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address (or comma-separated list)"},
                "subject": {"type": "string"},
                "body": {"type": "string", "description": "Plain-text email body"},
                "cc": {"type": "string", "description": "Optional CC address(es), comma-separated"},
            },
            "required": ["to", "subject", "body"],
        },
    },
}

EMAIL_FETCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "email_fetch",
        "description": "Fetch recent emails from this company's configured IMAP inbox.",
        "parameters": {
            "type": "object",
            "properties": {
                "folder": {"type": "string", "description": "IMAP folder name. Default: INBOX", "default": "INBOX"},
                "limit": {"type": "integer", "description": "Max emails to fetch (1–50). Default 10.", "default": 10},
                "unread_only": {"type": "boolean", "description": "Fetch only unread emails. Default false.", "default": False},
            },
            "required": [],
        },
    },
}

WEB_SEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the live web using Brave Search. Use this to find current information, "
            "news, documentation, prices, or anything not in the company knowledge base."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "count": {
                    "type": "integer",
                    "description": "Number of results (1–10). Default 5.",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
}

COMPANY_TOOL_SCHEMAS = [RAG_SEARCH_SCHEMA, EMAIL_SEND_SCHEMA, EMAIL_FETCH_SCHEMA, WEB_SEARCH_SCHEMA]


# ── Implementations ───────────────────────────────────────────────────────────

def rag_search(company_ctx: dict, company_folder: str, query: str, limit: int = 5) -> str:
    from app.rag.store import search
    limit = max(1, min(limit, 10))
    try:
        results = search(company_ctx["company_id"], query, limit=limit)
    except Exception as e:
        return f"Knowledge base search error: {e}"
    if not results:
        return "No relevant documents found in the knowledge base."
    parts = []
    for i, r in enumerate(results, 1):
        score = f" (score: {r['score']})" if r["score"] is not None else ""
        header = f"[{i}] {r['filename']}{score} — chunk {r['chunk_index'] + 1}/{r['total_chunks']}"
        parts.append(f"{header}\n{r['text']}")
    return "\n\n---\n\n".join(parts)


def _company_ns(company_ctx: dict):
    """Build a SimpleNamespace that email_client functions accept in place of a Company ORM row."""
    return types.SimpleNamespace(**company_ctx)


def email_send(company_ctx: dict, company_folder: str, to: str, subject: str, body: str, cc: str = "") -> str:
    from app.email_client import send_email
    ns = _company_ns(company_ctx)
    to_list = [a.strip() for a in to.split(",") if a.strip()]
    cc_list = [a.strip() for a in cc.split(",") if a.strip()] if cc else None
    try:
        send_email(ns, to=to_list, subject=subject, body=body, cc=cc_list or None)
    except ValueError as e:
        return f"Email not configured: {e}"
    except Exception as e:
        return f"Failed to send email: {e}"
    return f"Email sent to {', '.join(to_list)}."


def email_fetch(company_ctx: dict, company_folder: str, folder: str = "INBOX", limit: int = 10, unread_only: bool = False) -> str:
    from app.email_client import fetch_emails
    ns = _company_ns(company_ctx)
    limit = max(1, min(limit, 50))
    try:
        emails = fetch_emails(ns, folder=folder, limit=limit, unread_only=unread_only)
    except ValueError as e:
        return f"Email not configured: {e}"
    except Exception as e:
        return f"Failed to fetch emails: {e}"
    if not emails:
        return f"No {'unread ' if unread_only else ''}emails found in {folder}."
    lines = []
    for i, m in enumerate(emails, 1):
        body_preview = (m["body"] or "").strip().replace("\n", " ")[:200]
        lines.append(
            f"[{i}] From: {m['from']}\n"
            f"    Date: {m['date']}\n"
            f"    Subject: {m['subject']}\n"
            f"    Body: {body_preview}{'…' if len(m['body'] or '') > 200 else ''}"
        )
    return "\n\n".join(lines)


BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


def web_search(company_ctx: dict, company_folder: str, query: str, count: int = 5) -> str:
    import httpx
    from app.crypto import decrypt

    encrypted_key = company_ctx.get("brave_api_key_encrypted")
    if not encrypted_key:
        return (
            "Web search is not available: no Brave Search API key configured for this company. "
            "Add one in Company Settings → Web Search."
        )

    try:
        api_key = decrypt(encrypted_key)
    except Exception:
        return "Web search error: could not decrypt API key."

    count = max(1, min(count, 10))

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                BRAVE_SEARCH_URL,
                headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
                params={"q": query, "count": count},
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        if code in (401, 422):
            return "Web search failed: invalid Brave API key — check your key in Company Settings."
        if code == 429:
            return "Web search failed: rate limit exceeded. Monthly free quota (2,000 requests) may be exhausted."
        return f"Web search failed: HTTP {code}"
    except Exception as e:
        return f"Web search error: {e}"

    results = (resp.json().get("web") or {}).get("results") or []
    if not results:
        return f"No web results found for: {query}"

    parts = []
    for i, r in enumerate(results, 1):
        parts.append(f"[{i}] {r.get('title', '')}\n{r.get('url', '')}\n{r.get('description', '')}")
    return "\n\n".join(parts)


COMPANY_TOOL_IMPLS: dict[str, callable] = {
    "rag_search": rag_search,
    "email_send": email_send,
    "email_fetch": email_fetch,
    "web_search": web_search,
}
