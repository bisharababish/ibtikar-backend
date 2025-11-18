from cryptography.fernet import Fernet
from .config import settings
import re

# Strip all whitespace (spaces, newlines, tabs, etc.) and validate FERNET_KEY
_fernet_key = re.sub(r'\s+', '', settings.FERNET_KEY)
if len(_fernet_key) != 44:
    raise ValueError(
        f"Invalid FERNET_KEY length: {len(_fernet_key)} characters (expected 44). "
        f"Key must be exactly 44 characters (32 bytes base64-encoded). "
        f"Please check your FERNET_KEY environment variable in Render and ensure it has no extra spaces or newlines. "
        f"Generate a new key with: from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    )
try:
    _f = Fernet(_fernet_key.encode())
except ValueError as e:
    raise ValueError(
        f"Invalid FERNET_KEY format: {e}. "
        f"FERNET_KEY must be 32 url-safe base64-encoded bytes (44 characters). "
        f"Current key (after stripping whitespace): {len(_fernet_key)} characters. "
        f"Generate a new key with: from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ) from e

def enc(s: str) -> bytes:
    return _f.encrypt(s.encode())

def dec(b: bytes) -> str:
    return _f.decrypt(b).decode()
