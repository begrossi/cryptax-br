import base64
import json
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import settings

# Legacy shared salt (same for every install). Kept ONLY as a decrypt fallback so
# credentials stored by older versions still open. Never used for new writes.
_LEGACY_SALT = b"cryptax-br-salt-v1"

# Per-install random salt, generated once and persisted next to the DB.
_salt_cache: bytes | None = None


class InsecureSecretKeyError(ValueError):
    """Raised when credentials would be encrypted under the public default key."""


def _salt_path() -> Path:
    """Location of the per-install salt file — next to the SQLite DB when possible."""
    prefix = "sqlite+aiosqlite:///"
    url = settings.database_url
    if url.startswith(prefix):
        db_path = url[len(prefix):]  # './cryptax.db' or '/app/data/cryptax.db'
        return Path(db_path).resolve().parent / ".crypto_salt"
    return Path("./.crypto_salt").resolve()


def _get_salt() -> bytes:
    """Return this install's salt, generating and persisting it on first use."""
    global _salt_cache
    if _salt_cache is not None:
        return _salt_cache
    path = _salt_path()
    if path.exists():
        _salt_cache = path.read_bytes()
        return _salt_cache
    salt = secrets.token_bytes(16)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(salt)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # best effort (e.g. Windows)
    _salt_cache = salt
    return salt


def _fernet(salt: bytes) -> Fernet:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100_000)
    key = base64.urlsafe_b64encode(kdf.derive(settings.secret_key.encode()))
    return Fernet(key)


def encrypt_credentials(data: dict) -> str:
    if settings.secret_key_is_default:
        raise InsecureSecretKeyError(
            "SECRET_KEY is still the default placeholder — refusing to store API "
            "credentials that anyone with the source could decrypt. Set SECRET_KEY "
            "to a random value (openssl rand -hex 32) and restart."
        )
    return _fernet(_get_salt()).encrypt(json.dumps(data).encode()).decode()


def decrypt_credentials(token: str) -> dict:
    raw = token.encode()
    try:
        return json.loads(_fernet(_get_salt()).decrypt(raw))
    except InvalidToken:
        # Credentials written before per-install salts used the shared legacy salt.
        return json.loads(_fernet(_LEGACY_SALT).decrypt(raw))
