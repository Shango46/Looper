import subprocess


def get_tailscale_ip() -> str | None:
    """Best-effort detection of this machine's Tailscale IPv4 address, for display only."""
    try:
        proc = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            ip = proc.stdout.strip().splitlines()[0].strip() if proc.stdout.strip() else None
            return ip or None
    except Exception:
        pass
    return None
