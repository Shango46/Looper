import logging
import tempfile
from contextlib import asynccontextmanager
from datetime import timedelta

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.exceptions import McpError

from app.db.models import McpServer

logger = logging.getLogger("looper.mcp.client")

CALL_TOOL_TIMEOUT_SECONDS = 60
MAX_RESULT_CHARS = 8000


class McpToolError(Exception):
    pass


def _find_mcp_error(exc: BaseException) -> McpError | None:
    """Errors raised inside the yielded `async with _connect(...)` body (e.g. a call_tool
    timeout) get thrown back into this generator at the yield point, so they pass through the
    same except-block that handles real connection failures — anyio's TaskGroup also tends to
    wrap them in an ExceptionGroup along the way. Unwrap to find the original McpError, if any,
    so callers can distinguish 'the call itself failed/timed out' from 'could not connect'."""
    seen: set[int] = set()
    stack = [exc]
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, McpError):
            return current
        if isinstance(current, BaseExceptionGroup):
            stack.extend(current.exceptions)
        if current.__cause__:
            stack.append(current.__cause__)
    return None


@asynccontextmanager
async def _connect(server: McpServer):
    """Yields an initialized ClientSession. Connects fresh every time — no persistent
    session is held across calls, by design (see plan: simpler lifecycle, no stale-connection
    bugs, acceptable per-call reconnect cost for a personal-use tool)."""
    if server.transport == "stdio":
        # subprocess stderr redirection needs a real OS file descriptor — a plain io.StringIO()
        # has no fileno() and fails (most visibly on Windows, but no in-memory buffer works here
        # on any platform). A temp file gives us a real fd plus a way to read captured stderr back.
        params = StdioServerParameters(
            command=server.command,
            args=server.args_json or [],
            env=server.env_json or None,
        )
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as errlog:
            try:
                async with stdio_client(params, errlog=errlog) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        yield session
            except Exception as e:
                mcp_error = _find_mcp_error(e)
                if mcp_error:
                    raise mcp_error from e
                errlog.seek(0)
                stderr_output = errlog.read().strip()
                detail = f"{e}" + (f" (stderr: {stderr_output[:500]})" if stderr_output else "")
                raise McpToolError(f"MCP server '{server.name}' connection failed: {detail}") from e

    elif server.transport == "streamable_http":
        try:
            async with streamablehttp_client(url=server.url) as (read, write, _get_session_id):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
        except Exception as e:
            mcp_error = _find_mcp_error(e)
            if mcp_error:
                raise mcp_error from e
            raise McpToolError(f"MCP server '{server.name}' connection failed: {e}") from e

    else:
        raise McpToolError(f"Unknown MCP transport '{server.transport}' for server '{server.name}'.")


async def discover_tools(server: McpServer) -> list[dict]:
    """Connects once, lists tools, returns JSON-serializable dicts for caching.
    Does NOT execute anything — safe to call from a 'Refresh tools' button."""
    async with _connect(server) as session:
        result = await session.list_tools()
        return [
            {
                "name": t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema or {"type": "object", "properties": {}},
            }
            for t in result.tools
        ]


def _extract_text(call_result) -> str:
    texts = []
    non_text_count = 0
    for block in call_result.content:
        text = getattr(block, "text", None)
        if text is not None:
            texts.append(text)
        else:
            non_text_count += 1
    out = "\n".join(texts)
    if non_text_count:
        out += f"\n[{non_text_count} non-text content block(s) returned — not displayable here.]"
    if call_result.isError:
        out = f"Tool reported an error: {out}"
    return out or "(empty result)"


async def call_tool(server: McpServer, tool_name: str, args: dict) -> str:
    """Connects fresh, calls the tool with the SDK's own anyio-native read timeout (NOT
    asyncio.wait_for around the whole connection — that can orphan the stdio subprocess by
    cancelling mid-shutdown-sequence; the SDK's own timeout raises a clean McpError instead
    and lets the connection's normal context-manager teardown run, which does the real
    SIGTERM/SIGKILL escalation safely)."""
    try:
        async with _connect(server) as session:
            result = await session.call_tool(
                tool_name, arguments=args, read_timeout_seconds=timedelta(seconds=CALL_TOOL_TIMEOUT_SECONDS)
            )
            text = _extract_text(result)
            if len(text) > MAX_RESULT_CHARS:
                text = text[:MAX_RESULT_CHARS] + f"\n...[truncated, {len(text)} chars total]"
            return text
    except McpError as e:
        return f"MCP error calling '{tool_name}' on '{server.name}': {e}"
    except McpToolError as e:
        return str(e)
    except Exception as e:
        logger.exception("Unexpected error calling MCP tool %s on %s", tool_name, server.name)
        return f"Unexpected error calling '{tool_name}' on '{server.name}': {e}"
