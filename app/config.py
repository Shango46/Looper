from pathlib import Path

from cryptography.fernet import Fernet

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "looper.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

KEY_PATH = DATA_DIR / "secret.key"


def get_or_create_fernet_key() -> bytes:
    if KEY_PATH.exists():
        return KEY_PATH.read_bytes()
    key = Fernet.generate_key()
    KEY_PATH.write_bytes(key)
    return key


FERNET = Fernet(get_or_create_fernet_key())

# Agent runtime tuning
MAX_COMPANIES = 10
MAX_AGENTS_PER_COMPANY = 50
MEMORY_RETENTION_PER_AGENT = 1000
MAX_TOOL_ITERATIONS = 25
TASK_WALL_CLOCK_TIMEOUT_SECONDS = 600
WORKER_CONCURRENCY = 3
SHELL_OUTPUT_MAX_CHARS = 8000
HEARTBEAT_POLL_INTERVAL_SECONDS = 30
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

GITHUB_REPO = "Shango46/Looper"
VERSION_FILE = BASE_DIR / "VERSION"
PUBLISHER_TOKEN_PATH = BASE_DIR / "publisher.token"
IS_PUBLISHER = PUBLISHER_TOKEN_PATH.exists()


def get_publisher_token() -> str | None:
    if PUBLISHER_TOKEN_PATH.exists():
        return PUBLISHER_TOKEN_PATH.read_text(encoding="utf-8").strip() or None
    return None
