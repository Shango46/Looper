import time

# In-memory only — resets on process restart. This guards against rapid brute-forcing of the
# 8-char code within a single run; it is not a durable security control on its own. The real
# boundary for this feature is "must already be on the Tailscale tailnet to reach the server."
MAX_ATTEMPTS = 10
WINDOW_SECONDS = 300

_attempts: dict[str, list[float]] = {}


def check_and_record(client_ip: str) -> bool:
    """Returns True if this IP is still allowed to attempt /connect, recording the attempt.
    Returns False if it has exceeded MAX_ATTEMPTS within WINDOW_SECONDS."""
    now = time.monotonic()
    history = [t for t in _attempts.get(client_ip, []) if now - t < WINDOW_SECONDS]
    if len(history) >= MAX_ATTEMPTS:
        _attempts[client_ip] = history
        return False
    history.append(now)
    _attempts[client_ip] = history
    return True
