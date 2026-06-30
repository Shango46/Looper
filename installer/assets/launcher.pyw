"""
Looper launcher — no console window (.pyw extension + pythonw.exe).
Starts the server if not already running, then opens the browser.
"""
import os
import socket
import subprocess
import sys
import time
import webbrowser

INSTALL_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON_W = os.path.join(INSTALL_DIR, ".venv", "Scripts", "pythonw.exe")
SERVER_SCRIPT = os.path.join(INSTALL_DIR, "run.py")
URL = "http://localhost:8731"


def server_ready() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 8731), timeout=1):
            return True
    except OSError:
        return False


def main():
    if not os.path.exists(PYTHON_W):
        _error(
            f"Python environment not found at:\n{PYTHON_W}\n\n"
            "Please re-run the Looper installer."
        )
        return

    if not server_ready():
        subprocess.Popen(
            [PYTHON_W, SERVER_SCRIPT],
            cwd=INSTALL_DIR,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait up to 15 seconds for the server to be ready
        for _ in range(30):
            time.sleep(0.5)
            if server_ready():
                break

    webbrowser.open(URL)


def _error(msg: str):
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Looper", msg)
    except Exception:
        pass  # Silently fail if tkinter is unavailable


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        _error(f"Looper failed to start:\n{exc}")
