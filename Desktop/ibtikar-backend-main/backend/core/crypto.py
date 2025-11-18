from cryptography.fernet import Fernet
from .config import settings

# Strip whitespace and validate FERNET_KEY
_fernet_key = settings.FERNET_KEY.strip()
try:
    _f = Fernet(_fernet_key.encode())
except ValueError as e:
    raise ValueError(
        f"Invalid FERNET_KEY: {e}. "
        f"FERNET_KEY must be 32 url-safe base64-encoded bytes. "
        f"Current key length: {len(_fernet_key)} characters. "
        f"Generate a new key with: from cryptography.fernet import Fernet; Fernet.generate_key()"
    ) from e

def enc(s: str) -> bytes:
    return _f.encrypt(s.encode())

def dec(b: bytes) -> str:
    return _f.decrypt(b).decode()
