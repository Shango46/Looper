from app.config import FERNET


def encrypt(value: str) -> str:
    return FERNET.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt(value: str) -> str:
    return FERNET.decrypt(value.encode("utf-8")).decode("utf-8")
