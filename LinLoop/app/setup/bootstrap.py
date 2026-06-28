import logging
import platform
import shutil
import subprocess
import sys

logger = logging.getLogger("looper.setup")

WINDOWS_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def detect_chrome() -> str | None:
    system = platform.system()
    if system == "Windows":
        for path in WINDOWS_CHROME_PATHS:
            if shutil.which(path) or _file_exists(path):
                return path
        return None
    # Linux/Mac: look for common binary names on PATH.
    for name in ("google-chrome", "google-chrome-stable", "chromium-browser", "chromium"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _file_exists(path: str) -> bool:
    from pathlib import Path

    return Path(path).exists()


def manual_install_hint() -> str:
    system = platform.system()
    if system == "Windows":
        return "Download and install Google Chrome from https://www.google.com/chrome/."
    if system == "Linux":
        return (
            "Install Google Chrome on Linux Mint with:\n"
            "  wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb\n"
            "  sudo apt install ./google-chrome-stable_current_amd64.deb\n"
            "(Looper will use Playwright's bundled Chromium instead if you skip this.)"
        )
    return "Install Google Chrome for your platform from https://www.google.com/chrome/."


def run_playwright_install_chromium() -> tuple[bool, str]:
    """Downloads Playwright's own Chromium build into the user-local cache. No admin/sudo required."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        ok = proc.returncode == 0
        output = (proc.stdout or "") + (proc.stderr or "")
        return ok, output[-3000:]
    except Exception as e:
        return False, str(e)


def run_playwright_install_deps() -> tuple[bool, str]:
    """Linux-only: installs OS-level shared libraries Playwright/Chrome need. Requires sudo — surfaced
    to the user rather than run silently, consistent with the app's system-change approval philosophy."""
    if platform.system() != "Linux":
        return True, "Not needed on this OS."
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "playwright", "install-deps"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        return proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
    except Exception as e:
        return False, str(e)


def check_environment() -> dict:
    chrome_path = detect_chrome()
    try:
        from playwright.sync_api import sync_playwright

        playwright_installed = True
    except ImportError:
        playwright_installed = False

    chromium_cached = False
    if playwright_installed:
        try:
            with sync_playwright() as pw:
                chromium_cached = bool(pw.chromium.executable_path) and _file_exists(pw.chromium.executable_path)
        except Exception:
            chromium_cached = False

    return {
        "platform": platform.system(),
        "chrome_path": chrome_path,
        "chrome_found": bool(chrome_path),
        "playwright_installed": playwright_installed,
        "chromium_fallback_ready": chromium_cached,
        "manual_install_hint": manual_install_hint(),
        "ready": bool(chrome_path) or chromium_cached,
    }
