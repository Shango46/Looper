"""Manages the n8n background process — start, health-check, shutdown."""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

import httpx

from app.config import DATA_DIR, N8N_PORT, N8N_URL

logger = logging.getLogger("looper.n8n.process")

N8N_DATA_DIR: Path = DATA_DIR / "n8n"
_proc: subprocess.Popen | None = None


def _find_n8n() -> str | None:
    # Augment PATH with user-local bin dirs so shutil.which can find user-installed n8n
    home = Path.home()
    extra_paths = [
        str(home / ".local" / "bin"),    # Linux: npm prefix ~/.local used by install.sh
        str(home / ".nvm" / "versions"),  # nvm — shutil.which won't recurse, but shlex PATH will
    ]
    env_path = os.environ.get("PATH", "")
    augmented = os.pathsep.join(extra_paths) + os.pathsep + env_path
    found = shutil.which("n8n", path=augmented)
    if found:
        return found
    # Explicit fallback locations
    candidates: list[Path] = [
        home / ".local" / "bin" / "n8n",
        Path("/usr/local/bin/n8n"),
        Path("/usr/bin/n8n"),
    ]
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        for name in ("n8n.cmd", "n8n"):
            candidates.append(Path(appdata) / "npm" / name)
    for c in candidates:
        if c.exists():
            return str(c)
    return None


async def _wait_ready(timeout: int = 90) -> bool:
    async with httpx.AsyncClient() as client:
        for _ in range(timeout * 2):
            try:
                r = await client.get(f"{N8N_URL}/healthz", timeout=2.0)
                if r.status_code == 200:
                    return True
            except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError):
                pass
            await asyncio.sleep(0.5)
    return False


def _port_open() -> bool:
    import socket
    try:
        with socket.create_connection(("127.0.0.1", N8N_PORT), timeout=1):
            return True
    except OSError:
        return False


def start_n8n() -> bool:
    """Launch n8n as a detached background process. Returns False if n8n not found."""
    global _proc
    if _proc is not None and _proc.poll() is None:
        return True

    # n8n may already be running from a previous Looper process — don't start a second copy
    if _port_open():
        logger.info("n8n already listening on port %s", N8N_PORT)
        return True

    exe = _find_n8n()
    if not exe:
        logger.warning("n8n executable not found — automations unavailable")
        return False

    N8N_DATA_DIR.mkdir(parents=True, exist_ok=True)

    env = {
        **os.environ,
        "N8N_USER_FOLDER": str(N8N_DATA_DIR),
        "N8N_PORT": str(N8N_PORT),
        "N8N_HOST": "127.0.0.1",
        "N8N_EDITOR_BASE_URL": N8N_URL,
        "N8N_LOG_LEVEL": "warn",
        "N8N_SKIP_WEBHOOK_DEREGISTRATION_SHUTDOWN": "true",
        "N8N_HIRING_BANNER_ENABLED": "false",
        "N8N_VERSION_NOTIFICATIONS_ENABLED": "false",
        "N8N_DIAGNOSTICS_ENABLED": "false",
        # Tell n8n not to show the first-run owner-setup wizard — Looper creates the
        # owner account programmatically via the REST API in n8n_client.ensure_setup().
        "N8N_SKIP_OWNER_SETUP": "true",
        "WEBHOOK_URL": N8N_URL,
    }

    kwargs: dict = {
        "env": env,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        # .cmd files can't be Popen'd directly on Windows — wrap in cmd.exe
        if exe.lower().endswith(".cmd"):
            cmd = ["cmd.exe", "/c", exe, "start"]
        else:
            cmd = [exe, "start"]
    else:
        cmd = [exe, "start"]

    _proc = subprocess.Popen(cmd, **kwargs)
    logger.info("n8n process started (pid=%s)", _proc.pid)
    return True


async def start_n8n_async() -> bool:
    """Start n8n and wait until its HTTP server is ready. Returns True on success."""
    if not start_n8n():
        return False
    ready = await _wait_ready()
    if ready:
        logger.info("n8n ready at %s", N8N_URL)
    else:
        logger.warning("n8n did not become ready within timeout")
    return ready


def stop_n8n() -> None:
    global _proc
    if _proc is not None:
        try:
            _proc.terminate()
            _proc.wait(timeout=10)
        except Exception:
            try:
                _proc.kill()
            except Exception:
                pass
        _proc = None
        logger.info("n8n stopped")


def is_running() -> bool:
    if _proc is not None and _proc.poll() is None:
        return True
    return _port_open()
