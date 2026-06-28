import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.agents.paths import resolve_path

logger = logging.getLogger("looper.agents.browser")

_executors: dict[int, ThreadPoolExecutor] = {}
_state: dict[int, dict] = {}

MAX_TEXT_CHARS = 15000

BROWSER_NAVIGATE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "browser_navigate",
        "description": "Navigate the company's browser session to a URL and return the page title.",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
    },
}

BROWSER_GET_TEXT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "browser_get_text",
        "description": "Get the visible text content of the current page, or of a CSS selector if given.",
        "parameters": {"type": "object", "properties": {"selector": {"type": "string"}}, "required": []},
    },
}

BROWSER_CLICK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "browser_click",
        "description": "Click an element on the current page matched by a CSS selector.",
        "parameters": {"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]},
    },
}

BROWSER_FILL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "browser_fill",
        "description": "Type text into an input/textarea matched by a CSS selector.",
        "parameters": {
            "type": "object",
            "properties": {"selector": {"type": "string"}, "text": {"type": "string"}},
            "required": ["selector", "text"],
        },
    },
}

BROWSER_SCREENSHOT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "browser_screenshot",
        "description": "Save a screenshot of the current page into the company folder. Returns the saved filename.",
        "parameters": {"type": "object", "properties": {"filename": {"type": "string", "default": "screenshot.png"}}, "required": []},
    },
}

BROWSER_SCHEMAS = [
    BROWSER_NAVIGATE_SCHEMA,
    BROWSER_GET_TEXT_SCHEMA,
    BROWSER_CLICK_SCHEMA,
    BROWSER_FILL_SCHEMA,
    BROWSER_SCREENSHOT_SCHEMA,
]
BROWSER_TOOL_NAMES = {s["function"]["name"] for s in BROWSER_SCHEMAS}


def _get_executor(company_id: int) -> ThreadPoolExecutor:
    if company_id not in _executors:
        _executors[company_id] = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"browser-co{company_id}")
    return _executors[company_id]


def _ensure_page(company_id: int):
    state = _state.get(company_id)
    if state and state.get("page"):
        return state["page"]

    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    browser = None
    used_channel = None
    for channel in ("chrome", None):
        try:
            browser = pw.chromium.launch(channel=channel, headless=True) if channel else pw.chromium.launch(headless=True)
            used_channel = channel or "bundled-chromium"
            break
        except Exception as e:
            logger.warning("Browser launch with channel=%s failed: %s", channel, e)
    if not browser:
        pw.stop()
        raise RuntimeError("Could not launch a browser (system Chrome or bundled Chromium both failed).")

    page = browser.new_page()
    _state[company_id] = {"pw": pw, "browser": browser, "page": page, "channel": used_channel}
    return page


def _navigate(company_id: int, url: str) -> str:
    page = _ensure_page(company_id)
    page.goto(url, wait_until="load", timeout=30000)
    return f"Navigated to {url}\nTitle: {page.title()}"


def _get_text(company_id: int, selector: str | None = None) -> str:
    page = _ensure_page(company_id)
    text = page.locator(selector).inner_text() if selector else page.locator("body").inner_text()
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + f"\n...[truncated, {len(text)} chars total]"
    return text


def _click(company_id: int, selector: str) -> str:
    page = _ensure_page(company_id)
    page.locator(selector).click(timeout=10000)
    return f"Clicked '{selector}'."


def _fill(company_id: int, selector: str, text: str) -> str:
    page = _ensure_page(company_id)
    page.locator(selector).fill(text, timeout=10000)
    return f"Filled '{selector}'."


def _screenshot(company_id: int, company_folder: str, filename: str = "screenshot.png") -> str:
    page = _ensure_page(company_id)
    target = resolve_path(company_folder, filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(target))
    return f"Saved screenshot to '{filename}'."


async def dispatch_browser_tool(name: str, company_id: int, company_folder: str, args: dict) -> str:
    loop = asyncio.get_running_loop()
    executor = _get_executor(company_id)
    try:
        if name == "browser_navigate":
            return await loop.run_in_executor(executor, _navigate, company_id, args.get("url", ""))
        if name == "browser_get_text":
            return await loop.run_in_executor(executor, _get_text, company_id, args.get("selector"))
        if name == "browser_click":
            return await loop.run_in_executor(executor, _click, company_id, args.get("selector", ""))
        if name == "browser_fill":
            return await loop.run_in_executor(executor, _fill, company_id, args.get("selector", ""), args.get("text", ""))
        if name == "browser_screenshot":
            return await loop.run_in_executor(
                executor, _screenshot, company_id, company_folder, args.get("filename", "screenshot.png")
            )
        return f"Error: unknown browser tool '{name}'."
    except Exception as e:
        return f"Error in {name}: {e}"


def _close_company_browser(company_id: int) -> None:
    state = _state.pop(company_id, None)
    if state:
        try:
            state["browser"].close()
            state["pw"].stop()
        except Exception:
            pass


async def close_all_browsers() -> None:
    loop = asyncio.get_running_loop()
    for company_id in list(_state.keys()):
        executor = _get_executor(company_id)
        await loop.run_in_executor(executor, _close_company_browser, company_id)
    for executor in _executors.values():
        executor.shutdown(wait=False)
    _executors.clear()
