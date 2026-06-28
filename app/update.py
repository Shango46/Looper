import logging
import os
import subprocess
import sys
import threading
import time
from typing import Optional

import httpx

from app.config import BASE_DIR, GITHUB_REPO, VERSION_FILE

logger = logging.getLogger(__name__)


def get_local_version() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "0.0.0"


def has_git() -> bool:
    return (BASE_DIR / ".git").exists()


def _parse_version(v: str) -> tuple[int, ...]:
    v = v.lstrip("v")
    try:
        return tuple(int(x) for x in v.split("."))
    except Exception:
        return (0, 0, 0)


def is_newer(remote: str, local: str) -> bool:
    return _parse_version(remote) > _parse_version(local)


def next_patch(v: str) -> str:
    parts = v.split(".")
    if len(parts) == 3:
        try:
            return f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"
        except Exception:
            pass
    return v


async def get_latest_release() -> Optional[dict]:
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                return resp.json()
    except Exception as exc:
        logger.warning("GitHub release check failed: %s", exc)
    return None


def _run_git(args: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode == 0, (result.stdout + result.stderr).strip()
    except Exception as exc:
        return False, str(exc)


async def publish_release(
    version: str, changelog: str, token: str, apk_path: str | None = None,
    apk_version: str = "", apk_changelog: str = "",
) -> tuple[bool, str]:
    if not has_git():
        return False, "Git repository not initialised. See the publisher setup steps in Settings."

    VERSION_FILE.write_text(version, encoding="utf-8")

    ok, log = _run_git(["add", "-A"])
    if not ok:
        return False, f"git add failed: {log}"

    ok, log = _run_git(["commit", "-m", f"Release v{version}"])
    if not ok and "nothing to commit" not in log.lower():
        return False, f"git commit failed: {log}"

    ok, log = _run_git(["push", "origin", "main"])
    if not ok:
        return False, f"git push failed: {log}"

    api_headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    body = changelog
    if apk_version or apk_changelog:
        body += "\n\n---\n## Android App"
        if apk_version:
            body += f" v{apk_version}"
        if apk_changelog:
            body += f"\n{apk_changelog}"
    payload = {"tag_name": f"v{version}", "name": f"v{version}", "body": body, "target_commitish": "main"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.github.com/repos/{GITHUB_REPO}/releases",
                headers=api_headers,
                json=payload,
                timeout=30,
            )
            data = resp.json()
            if resp.status_code not in (200, 201):
                return False, f"GitHub API {resp.status_code}: {data.get('message', resp.text[:200])}"

            release_url = data.get("html_url", f"v{version} published successfully")

            # Upload APK asset if a path was provided
            if apk_path:
                from pathlib import Path
                apk = Path(apk_path)
                if apk.exists() and apk.suffix.lower() == ".apk":
                    release_id = data["id"]
                    upload_url = (
                        f"https://uploads.github.com/repos/{GITHUB_REPO}"
                        f"/releases/{release_id}/assets?name={apk.name}"
                    )
                    upload_headers = {
                        **api_headers,
                        "Content-Type": "application/vnd.android.package-archive",
                    }
                    up = await client.post(
                        upload_url,
                        headers=upload_headers,
                        content=apk.read_bytes(),
                        timeout=300,
                    )
                    if up.status_code not in (200, 201):
                        return True, f"Release published but APK upload failed ({up.status_code}): {release_url}"
                else:
                    return True, f"Release published but APK not found at path '{apk_path}': {release_url}"

            return True, release_url
    except Exception as exc:
        return False, f"GitHub API error: {exc}"


async def apply_update() -> tuple[bool, str]:
    if not has_git():
        return False, "Git repository not initialised — cannot pull updates."

    ok, log = _run_git(["pull", "origin", "main"])
    if not ok:
        return False, f"git pull failed: {log}"

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--quiet"],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            return False, f"pip install failed: {(result.stdout + result.stderr)[:500]}"
    except Exception as exc:
        return False, f"pip install error: {exc}"

    return True, "Update applied successfully. Click Restart to load the new code."


def schedule_restart(delay: float = 1.5) -> None:
    def _do():
        time.sleep(delay)
        os.chdir(str(BASE_DIR))
        os.execv(sys.executable, [sys.executable, str(BASE_DIR / "run.py")])

    threading.Thread(target=_do, daemon=True).start()
