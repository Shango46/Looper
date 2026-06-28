import re
from pathlib import Path
from typing import Literal

from app.agents.paths import is_inside_folder, resolve_path

Decision = Literal["ALLOW", "REQUIRE_APPROVAL"]

# Heuristic, best-effort guardrails — NOT a hard security boundary. Agents run with real shell
# access by explicit design choice; this only catches the patterns below, not every risky command.
SHELL_RISK_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bsudo\b", re.I), "uses sudo (elevated privileges)"),
    (re.compile(r"\brm\s+-rf?\s+/(?!\S)", re.I), "recursive delete at filesystem root"),
    (re.compile(r"\bmkfs\b|\bdd\s+if=", re.I), "disk-level formatting/imaging command"),
    (re.compile(r"\b(reg|reg\.exe)\s+(add|delete)\b", re.I), "modifies the Windows Registry"),
    (re.compile(r"\bbcdedit\b|\bdiskpart\b|\bpnputil\b", re.I), "modifies boot config, disks, or drivers"),
    (re.compile(r"\bshutdown\b|\bformat\s+[a-z]:", re.I), "shuts down or formats a drive"),
    (re.compile(r"\b(net\s+user|useradd|passwd)\b", re.I), "modifies OS user accounts"),
    (re.compile(r"\b(systemctl\s+(disable|stop)|service\s+\w+\s+stop)\b", re.I), "disables a system service"),
    (re.compile(r"\b(apt(-get)?\s+(remove|purge)|dpkg\s+-P|yum\s+remove)\b", re.I), "removes installed system packages"),
    (re.compile(r"\bchmod\s+-R\s+777\s+/(?!\S)", re.I), "recursively opens permissions at filesystem root"),
    (re.compile(r"/etc/|/boot/|/sys/|/dev/", re.I), "touches a Linux system directory"),
    (re.compile(r"c:\\windows|c:\\program files|system32|drivers", re.I), "touches a Windows system directory"),
]

def _command_touches_path_outside(command: str, company_folder: str) -> bool:
    """Best-effort scan for absolute paths in a shell command that resolve outside the company folder."""
    candidates = re.findall(r"[A-Za-z]:\\[^\s\"']+|/[^\s\"']+", command)
    for c in candidates:
        try:
            resolved = Path(c).resolve()
        except Exception:
            continue
        if not is_inside_folder(company_folder, resolved):
            return True
    return False


ABS_PATH_PATTERN = re.compile(r"^[A-Za-z]:\\|^/|\.\./|\.\.\\")


def _iter_string_values(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_string_values(v)
    elif isinstance(value, list):
        for v in value:
            yield from _iter_string_values(v)


def _args_reference_path_outside(args: dict, company_folder: str) -> str | None:
    """Generic, tool-name-agnostic fallback: any string argument that looks like an absolute
    path or a '..' escape and resolves outside the company folder gets flagged. This matters
    most for MCP-provided tools, which evaluate_risk otherwise has zero specific knowledge of —
    without this, a filesystem-like MCP tool could escape the sandbox with no scrutiny at all."""
    for value in _iter_string_values(args):
        if not ABS_PATH_PATTERN.search(value):
            continue
        try:
            resolved = resolve_path(company_folder, value) if not Path(value).is_absolute() else Path(value).resolve()
        except Exception:
            continue
        if not is_inside_folder(company_folder, resolved):
            return value
    return None


def evaluate_risk(tool_name: str, args: dict, company_folder: str) -> tuple[Decision, str]:
    if tool_name == "shell_exec":
        command = str(args.get("command", ""))
        for pattern, reason in SHELL_RISK_PATTERNS:
            if pattern.search(command):
                return "REQUIRE_APPROVAL", f"Command {reason}: `{command}`"
        if _command_touches_path_outside(command, company_folder):
            return "REQUIRE_APPROVAL", f"Command references a path outside the company folder: `{command}`"
        return "ALLOW", ""

    if tool_name in ("file_read", "file_write", "file_list"):
        rel_path = args.get("path", ".")
        try:
            resolved = resolve_path(company_folder, rel_path)
        except Exception:
            return "REQUIRE_APPROVAL", f"Could not resolve path '{rel_path}'"
        if not is_inside_folder(company_folder, resolved):
            return "REQUIRE_APPROVAL", f"Path '{rel_path}' resolves outside the company folder ({resolved})"
        return "ALLOW", ""

    # Generic fallback for every other tool (including all MCP-provided tools, which this
    # function otherwise has zero specific knowledge of).
    escaping_value = _args_reference_path_outside(args, company_folder)
    if escaping_value:
        return "REQUIRE_APPROVAL", f"Tool '{tool_name}' argument references a path outside the company folder: `{escaping_value}`"
    return "ALLOW", ""
