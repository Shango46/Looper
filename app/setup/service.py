import platform
import subprocess
import sys
from pathlib import Path

from app.config import BASE_DIR

TASK_NAME = "LooperBackgroundService"
SYSTEMD_UNIT_NAME = "looper.service"


def _systemd_unit_path() -> Path:
    return Path.home() / ".config" / "systemd" / "user" / SYSTEMD_UNIT_NAME


def _run(cmd: list[str]) -> tuple[bool, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
    except Exception as e:
        return False, str(e)


def install_service() -> tuple[bool, str]:
    """Installs an OS-level service so heartbeats keep firing without the app being manually launched.
    Windows: a per-user Scheduled Task at logon (no admin required). Linux: a systemd --user unit."""
    system = platform.system()
    python_exe = sys.executable
    run_py = str(BASE_DIR / "run.py")

    if system == "Windows":
        cmd = (
            f'schtasks /create /tn "{TASK_NAME}" '
            f'/tr "\\"{python_exe}\\" \\"{run_py}\\"" /sc onlogon /rl limited /f'
        )
        return _run_shell(cmd)

    if system == "Linux":
        unit_path = _systemd_unit_path()
        unit_path.parent.mkdir(parents=True, exist_ok=True)
        unit_path.write_text(
            f"[Unit]\nDescription=Looper background service\n\n"
            f"[Service]\nExecStart={python_exe} {run_py}\nWorkingDirectory={BASE_DIR}\nRestart=on-failure\n\n"
            f"[Install]\nWantedBy=default.target\n"
        )
        ok1, out1 = _run(["systemctl", "--user", "daemon-reload"])
        ok2, out2 = _run(["systemctl", "--user", "enable", "--now", SYSTEMD_UNIT_NAME])
        return ok1 and ok2, out1 + out2

    return False, f"Background service install is not implemented for {system}."


def _run_shell(cmd: str) -> tuple[bool, str]:
    try:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
    except Exception as e:
        return False, str(e)


def uninstall_service() -> tuple[bool, str]:
    system = platform.system()
    if system == "Windows":
        return _run_shell(f'schtasks /delete /tn "{TASK_NAME}" /f')
    if system == "Linux":
        ok, out = _run(["systemctl", "--user", "disable", "--now", SYSTEMD_UNIT_NAME])
        unit_path = _systemd_unit_path()
        if unit_path.exists():
            unit_path.unlink()
        return ok, out
    return False, f"Background service uninstall is not implemented for {system}."


def service_status() -> dict:
    system = platform.system()
    if system == "Windows":
        ok, out = _run_shell(f'schtasks /query /tn "{TASK_NAME}"')
        return {"platform": system, "installed": ok, "detail": out.strip()[:300]}
    if system == "Linux":
        ok, out = _run(["systemctl", "--user", "is-enabled", SYSTEMD_UNIT_NAME])
        return {"platform": system, "installed": ok, "detail": out.strip()[:300]}
    return {"platform": system, "installed": False, "detail": "Unsupported platform."}
