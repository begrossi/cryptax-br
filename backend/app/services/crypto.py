import base64
import json

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import settings

_SALT = b"cryptax-br-salt-v1"


class InsecureSecretKeyError(ValueError):
    """Raised when credentials would be encrypted under the public default key."""


def _fernet() -> Fernet:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=_SALT, iterations=100_000)
    key = base64.urlsafe_b64encode(kdf.derive(settings.secret_key.encode()))
    return Fernet(key)


def encrypt_credentials(data: dict) -> str:
    if settings.secret_key_is_default:
        raise InsecureSecretKeyError(
            "SECRET_KEY is still the default placeholder — refusing to store API "
            "credentials that anyone with the source could decrypt. Set SECRET_KEY "
            "to a random value (openssl rand -hex 32) and restart."
        )
    return _fernet().encrypt(json.dumps(data).encode()).decode()


def decrypt_credentials(token: str) -> dict:
    return json.loads(_fernet().decrypt(token.encode()))
