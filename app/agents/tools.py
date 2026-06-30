import subprocess

from app.agents.paths import resolve_path
from app.config import SHELL_OUTPUT_MAX_CHARS
from app.db.models import Agent

FILE_READ_SCHEMA = {
    "type": "function",
    "function": {
        "name": "file_read",
        "description": "Read a text file's contents. Path is relative to the company's working folder.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative file path"}},
            "required": ["path"],
        },
    },
}

FILE_WRITE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "file_write",
        "description": "Write or append text to a file. Creates parent directories if needed. Path is relative to the company's working folder.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"},
                "content": {"type": "string"},
                "mode": {"type": "string", "enum": ["overwrite", "append"], "default": "overwrite"},
            },
            "required": ["path", "content"],
        },
    },
}

FILE_LIST_SCHEMA = {
    "type": "function",
    "function": {
        "name": "file_list",
        "description": "List files and folders at a path relative to the company's working folder.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "default": "."}},
            "required": [],
        },
    },
}

SHELL_EXEC_SCHEMA = {
    "type": "function",
    "function": {
        "name": "shell_exec",
        "description": (
            "Run a shell command with full OS shell access (cmd.exe on Windows, sh on Linux), "
            "with the working directory set to the company's folder. Commands that touch paths "
            "outside the company folder, or that affect system config/registry/drivers/user accounts, "
            "will pause for explicit user approval before running."
        ),
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
}

MAX_FILE_READ_CHARS = 20000
SHELL_TIMEOUT_SECONDS = 120


def file_read(company_folder: str, path: str) -> str:
    target = resolve_path(company_folder, path)
    if not target.exists():
        return f"Error: '{path}' does not exist."
    if target.is_dir():
        return f"Error: '{path}' is a directory, not a file."
    text = target.read_text(encoding="utf-8", errors="replace")
    if len(text) > MAX_FILE_READ_CHARS:
        return text[:MAX_FILE_READ_CHARS] + f"\n...[truncated, {len(text)} chars total]"
    return text


def file_write(company_folder: str, path: str, content: str, mode: str = "overwrite") -> str:
    target = resolve_path(company_folder, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a" if mode == "append" else "w", encoding="utf-8") as f:
        f.write(content)
    return f"OK: wrote {len(content)} chars to '{path}' ({mode})."


def file_list(company_folder: str, path: str = ".") -> str:
    target = resolve_path(company_folder, path)
    if not target.exists():
        return f"Error: '{path}' does not exist."
    if target.is_file():
        return f"'{path}' is a file ({target.stat().st_size} bytes)."
    entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    lines = [f"{'[dir] ' if e.is_dir() else '[file]'} {e.name}" for e in entries]
    return "\n".join(lines) if lines else "(empty directory)"


def shell_exec(company_folder: str, command: str) -> str:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=company_folder,
            capture_output=True,
            text=True,
            timeout=SHELL_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {SHELL_TIMEOUT_SECONDS}s."

    out = f"exit_code: {proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    if len(out) > SHELL_OUTPUT_MAX_CHARS:
        out = out[:SHELL_OUTPUT_MAX_CHARS] + f"\n...[truncated, {len(out)} chars total]"
    return out


TOOL_IMPLS = {
    "file_read": file_read,
    "file_write": file_write,
    "file_list": file_list,
    "shell_exec": shell_exec,
}


def get_tools_for(agent: Agent, active_children: list[Agent] | None = None) -> list[dict]:
    """Dynamic tool schema composition. Skill-derived tools are layered on in loop.py."""
    from app.agents.browser import BROWSER_SCHEMAS
    from app.agents.company_tools import COMPANY_TOOL_SCHEMAS
    from app.agents.delegation import REPORT_TO_SUPERVISOR_SCHEMA, build_delegate_schema

    schemas = [FILE_READ_SCHEMA, FILE_WRITE_SCHEMA, FILE_LIST_SCHEMA, SHELL_EXEC_SCHEMA] + BROWSER_SCHEMAS + COMPANY_TOOL_SCHEMAS
    if active_children:
        schemas.append(build_delegate_schema(active_children))
    if agent.parent_agent_id is not None:
        schemas.append(REPORT_TO_SUPERVISOR_SCHEMA)
    return schemas


def get_tool_impl(name: str):
    return TOOL_IMPLS.get(name)
