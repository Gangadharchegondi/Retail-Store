"""Security helpers for password hashing and verification."""

import hashlib
import hmac
import os


_PBKDF2_ALGORITHM = "sha256"
_PBKDF2_ITERATIONS = 260000
_PBKDF2_PREFIX = "pbkdf2_sha256"


def hash_password(plain_password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256."""
    password = (plain_password or "").encode("utf-8")
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac(
        _PBKDF2_ALGORITHM,
        password,
        salt.encode("utf-8"),
        _PBKDF2_ITERATIONS,
    ).hex()
    return f"{_PBKDF2_PREFIX}${_PBKDF2_ITERATIONS}${salt}${digest}"


def is_hashed_password(value: str) -> bool:
    parts = str(value or "").split("$")
    return len(parts) == 4 and parts[0] == _PBKDF2_PREFIX


def verify_password(plain_password: str, stored_password: str) -> bool:
    """Verify hashed password, with fallback for legacy plaintext rows."""
    if not stored_password:
        return False

    if not is_hashed_password(stored_password):
        # Legacy fallback for old plain-text rows.
        return hmac.compare_digest(str(stored_password), str(plain_password or ""))

    try:
        prefix, iterations_str, salt, stored_digest = stored_password.split("$", 3)
        if prefix != _PBKDF2_PREFIX:
            return False

        iterations = int(iterations_str)
        computed_digest = hashlib.pbkdf2_hmac(
            _PBKDF2_ALGORITHM,
            (plain_password or "").encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        ).hex()
        return hmac.compare_digest(stored_digest, computed_digest)
    except Exception:
        return False
