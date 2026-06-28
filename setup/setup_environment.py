"""One-shot environment check/bootstrap. Run before first launch: python setup/setup_environment.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.setup.bootstrap import check_environment, run_playwright_install_chromium, run_playwright_install_deps


def main() -> None:
    env = check_environment()
    print(f"Platform: {env['platform']}")
    print(f"Google Chrome: {'found at ' + env['chrome_path'] if env['chrome_found'] else 'NOT FOUND'}")
    print(f"Playwright bundled Chromium ready: {env['chromium_fallback_ready']}")

    if not env["chrome_found"]:
        print("\n" + env["manual_install_hint"])
        print("\nInstalling Playwright's bundled Chromium as a fallback (no admin/sudo required)...")
        ok, log = run_playwright_install_chromium()
        print(log)
        if not ok:
            print("WARNING: bundled Chromium install failed. Browser tools may not work until this is resolved.")

    ok, log = run_playwright_install_deps()
    if log.strip():
        print(log)

    print("\nSetup check complete. Run `python run.py` to start Looper.")


if __name__ == "__main__":
    main()
