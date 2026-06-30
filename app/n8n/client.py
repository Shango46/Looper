"""n8n REST API client — handles first-run owner setup and all project/workflow calls."""
from __future__ import annotations

import logging
import secrets
from typing import TYPE_CHECKING

import httpx

from app.config import N8N_URL
from app.n8n.process import N8N_DATA_DIR

if TYPE_CHECKING:
    from app.db.models import Company

logger = logging.getLogger("looper.n8n.client")

_CREDS_FILE = N8N_DATA_DIR / ".looper_creds"
_API_KEY_FILE = N8N_DATA_DIR / ".looper_api_key"
_OWNER_EMAIL = "admin@looper.local"
_OWNER_FIRST = "Looper"
_OWNER_LAST = "Admin"


# ── Credential helpers ────────────────────────────────────────────────────────

def _get_or_create_password() -> str:
    if _CREDS_FILE.exists():
        return _CREDS_FILE.read_text().strip()
    # n8n requires ≥8 chars and at least one digit
    pwd = secrets.token_urlsafe(18) + str(secrets.randbelow(9000) + 1000)
    _CREDS_FILE.write_text(pwd)
    return pwd


def get_credentials() -> tuple[str, str] | None:
    """Return (email, password) for the self-hosted n8n owner account, or None if not set up."""
    if not _CREDS_FILE.exists():
        return None
    pwd = _CREDS_FILE.read_text().strip()
    return (_OWNER_EMAIL, pwd) if pwd else None


def load_api_key() -> str | None:
    if _API_KEY_FILE.exists():
        return _API_KEY_FILE.read_text().strip() or None
    return None


def save_api_key(key: str) -> None:
    _API_KEY_FILE.write_text(key)


# ── First-run setup ───────────────────────────────────────────────────────────

async def ensure_setup() -> bool:
    """
    Run first-time n8n owner account creation and API key generation.
    Safe to call repeatedly — checks for existing key first.
    Handles n8n v2 API conventions (emailOrLdapLoginId, cookie auth, scoped keys).
    """
    if load_api_key():
        return True

    password = _get_or_create_password()

    async with httpx.AsyncClient(base_url=N8N_URL, timeout=15.0, follow_redirects=True) as client:
        # 1. Create owner account — no-op if already exists (400 is fine)
        try:
            await client.post("/rest/owner/setup", json={
                "email": _OWNER_EMAIL,
                "firstName": _OWNER_FIRST,
                "lastName": _OWNER_LAST,
                "password": password,
                "agree": True,
            })
        except Exception as exc:
            logger.debug("n8n owner setup: %s", exc)

        # 2. Login — n8n v2 uses emailOrLdapLoginId and returns an HttpOnly cookie
        try:
            r = await client.post("/rest/login", json={
                "emailOrLdapLoginId": _OWNER_EMAIL,
                "password": password,
            })
            if r.status_code not in (200, 201):
                logger.warning("n8n login returned %s — manual setup required", r.status_code)
                return False
            # n8n v2: auth cookie is HttpOnly + Secure, so httpx drops it over HTTP.
            # Extract the raw cookie value from the Set-Cookie header and carry it manually.
            raw_cookie = r.headers.get("set-cookie", "")
            auth_cookie = next(
                (part.strip() for part in raw_cookie.split(";") if part.strip().startswith("n8n-auth=")),
                None,
            )
            if not auth_cookie:
                logger.warning("n8n login OK but no auth cookie found")
                return False
        except Exception as exc:
            logger.warning("n8n login failed: %s", exc)
            return False

        auth_headers = {"Cookie": auth_cookie}

        # 3. Fetch valid scopes for this n8n instance (n8n v2 requires explicit scopes)
        valid_scopes: list[str] = []
        try:
            rs = await client.get("/rest/api-keys/scopes", headers=auth_headers)
            if rs.status_code == 200:
                valid_scopes = rs.json().get("data", [])
        except Exception as exc:
            logger.debug("n8n scopes fetch: %s", exc)

        if not valid_scopes:
            # Fallback to a known-safe subset for n8n v1 / older installs
            valid_scopes = ["workflow:list", "workflow:read", "workflow:create",
                            "workflow:update", "workflow:delete", "project:list",
                            "project:read", "project:create", "project:update",
                            "project:delete"]

        # 4. Delete any stale looper-internal key so we can create a fresh one
        _LABEL = "looper-internal"
        try:
            rl = await client.get("/rest/api-keys", headers=auth_headers)
            if rl.status_code == 200:
                items = (rl.json().get("data") or {}).get("items", [])
                for item in items:
                    if item.get("label") == _LABEL:
                        await client.delete(f"/rest/api-keys/{item['id']}", headers=auth_headers)
                        logger.info("deleted stale n8n API key id=%s", item["id"])
        except Exception as exc:
            logger.debug("n8n stale key cleanup: %s", exc)

        # 5. Create a fresh long-lived API key
        import time as _time
        expires_ms = int((_time.time() + 10 * 365 * 24 * 3600) * 1000)
        key_body = {"label": _LABEL, "scopes": valid_scopes, "expiresAt": expires_ms}
        created = False
        for endpoint in ("/rest/api-keys", "/rest/user/api-keys", "/rest/user/api-key"):
            try:
                r = await client.post(endpoint, json=key_body, headers=auth_headers)
                if r.status_code in (200, 201):
                    body = r.json()
                    data = body.get("data") or body
                    # n8n v2 returns rawApiKey (the actual bearer token); apiKey is a truncated display value
                    key = data.get("rawApiKey") or data.get("apiKey") or body.get("apiKey", "")
                    if key:
                        save_api_key(key)
                        logger.info("n8n API key created and saved (len=%d)", len(key))
                        created = True
                        break
                # v1 fallback: try without scopes/expiresAt
                r = await client.post(endpoint, json={"label": _LABEL}, headers=auth_headers)
                if r.status_code in (200, 201):
                    body = r.json()
                    data = body.get("data") or body
                    key = data.get("rawApiKey") or data.get("apiKey") or body.get("apiKey", "")
                    if key:
                        save_api_key(key)
                        logger.info("n8n API key created (legacy endpoint) and saved (len=%d)", len(key))
                        created = True
                        break
            except Exception as exc:
                logger.debug("n8n API key endpoint %s: %s", endpoint, exc)

        if not created:
            logger.warning("n8n setup incomplete — open n8n and create an API key manually")
        return created


# ── Client factories ──────────────────────────────────────────────────────────

def _self_hosted_client() -> httpx.AsyncClient:
    key = load_api_key() or ""
    return httpx.AsyncClient(
        base_url=f"{N8N_URL}/api/v1",
        headers={"X-N8N-API-KEY": key},
        timeout=15.0,
    )


def get_client(company: "Company") -> httpx.AsyncClient:
    """Return an API client configured for the company's n8n mode."""
    if company.n8n_mode == "cloud" and company.n8n_cloud_url:
        from app.crypto import decrypt
        base = company.n8n_cloud_url.rstrip("/")
        key = decrypt(company.n8n_cloud_api_key_encrypted) if company.n8n_cloud_api_key_encrypted else ""
        return httpx.AsyncClient(
            base_url=f"{base}/api/v1",
            headers={"X-N8N-API-KEY": key},
            timeout=15.0,
        )
    return _self_hosted_client()


# ── Project / tag helpers ─────────────────────────────────────────────────────

def _company_tag(company: "Company") -> str:
    return f"looper-{company.id}"


async def create_project(company: "Company") -> str | None:
    """Try to create an n8n project (enterprise/cloud only).
    Returns project ID on success, or the sentinel 'tag:{tag}' for free self-hosted.
    """
    async with get_client(company) as client:
        try:
            r = await client.post("/projects", json={"name": company.name})
            if r.status_code in (200, 201):
                return r.json().get("id")
            if r.status_code in (403, 401):
                # Projects are a paid feature — fall back to tag-based isolation
                tag = _company_tag(company)
                logger.info("n8n projects not available (license); using tag '%s' for company %s", tag, company.id)
                return f"tag:{tag}"
            logger.warning("n8n create_project returned %s: %s", r.status_code, r.text[:200])
        except Exception as exc:
            logger.warning("n8n create_project error: %s", exc)
    return None


async def delete_project(company: "Company") -> bool:
    if not company.n8n_project_id:
        return True
    if company.n8n_project_id.startswith("tag:"):
        return True  # tag-based — nothing to delete in n8n
    async with get_client(company) as client:
        try:
            r = await client.delete(f"/projects/{company.n8n_project_id}")
            return r.status_code in (200, 204)
        except Exception as exc:
            logger.warning("n8n delete_project error: %s", exc)
    return False


# ── Workflow operations ───────────────────────────────────────────────────────

async def list_workflows(company: "Company") -> list[dict]:
    async with get_client(company) as client:
        try:
            if company.n8n_project_id and not company.n8n_project_id.startswith("tag:"):
                # Enterprise/cloud: filter by project
                r = await client.get("/workflows", params={"projectId": company.n8n_project_id, "limit": 100})
            else:
                # Free self-hosted (tag-based or not yet linked): show all workflows.
                # Tags are applied as soft markers for template-created workflows but we
                # don't filter by them since the user manages all workflows in n8n's UI.
                r = await client.get("/workflows", params={"limit": 100})
            if r.status_code == 200:
                return r.json().get("data", [])
        except Exception as exc:
            logger.warning("n8n list_workflows error: %s", exc)
    return []


async def create_workflow_from_json(company: "Company", workflow_json: dict) -> dict | None:
    """Push a workflow JSON template into the company's n8n project/tag."""
    payload = {**workflow_json}
    payload.pop("id", None)

    if company.n8n_project_id and not company.n8n_project_id.startswith("tag:"):
        payload["projectId"] = company.n8n_project_id

    async with get_client(company) as client:
        try:
            r = await client.post("/workflows", json=payload)
            if r.status_code in (200, 201):
                result = r.json()
                # For tag-based isolation, apply the company tag after creation
                if company.n8n_project_id and company.n8n_project_id.startswith("tag:"):
                    wid = (result.get("data") or result).get("id")
                    tag = company.n8n_project_id[4:]
                    if wid:
                        await _apply_tag(client, wid, tag)
                return result
            logger.warning("n8n create_workflow returned %s: %s", r.status_code, r.text[:200])
        except Exception as exc:
            logger.warning("n8n create_workflow_from_json error: %s", exc)
    return None


async def _apply_tag(client: "httpx.AsyncClient", workflow_id: str, tag_name: str) -> None:
    """Ensure tag_name exists and apply it to a workflow."""
    try:
        # Create or find the tag
        rt = await client.post("/tags", json={"name": tag_name})
        if rt.status_code in (200, 201):
            tag_id = (rt.json().get("data") or rt.json()).get("id")
        else:
            # Tag may already exist — list and find it
            rl = await client.get("/tags")
            tags = (rl.json().get("data") or []) if rl.status_code == 200 else []
            tag_id = next((t["id"] for t in tags if t.get("name") == tag_name), None)
        if tag_id:
            await client.put(f"/workflows/{workflow_id}/tags", json=[{"id": tag_id}])
    except Exception as exc:
        logger.debug("n8n _apply_tag error: %s", exc)


async def export_workflow(company: "Company", workflow_id: str) -> dict | None:
    """Export a workflow as portable JSON (strips runtime-specific fields)."""
    async with get_client(company) as client:
        try:
            r = await client.get(f"/workflows/{workflow_id}")
            if r.status_code == 200:
                data = r.json()
                for key in ("id", "createdAt", "updatedAt", "projectId", "active", "versionId"):
                    data.pop(key, None)
                return data
        except Exception as exc:
            logger.warning("n8n export_workflow error: %s", exc)
    return None


async def test_connection(base_url: str, api_key: str) -> bool:
    """Verify a cloud n8n instance is reachable with the given API key."""
    url = base_url.rstrip("/")
    async with httpx.AsyncClient(
        base_url=f"{url}/api/v1",
        headers={"X-N8N-API-KEY": api_key},
        timeout=8.0,
    ) as client:
        try:
            r = await client.get("/workflows", params={"limit": 1})
            return r.status_code == 200
        except Exception:
            return False


def project_ui_url(company: "Company") -> str:
    """Return the n8n UI URL deep-linked to this company's project."""
    if company.n8n_mode == "cloud" and company.n8n_cloud_url:
        base = company.n8n_cloud_url.rstrip("/")
    else:
        base = N8N_URL
    pid = company.n8n_project_id or ""
    if pid and not pid.startswith("tag:"):
        # Real project ID (enterprise/cloud) — n8n understands this URL param
        return f"{base}/home/workflows?projectId={pid}"
    # Tag-based or not yet linked — open general workflows page
    return f"{base}/home/workflows"
