# steg_studio/core/crypto.py
"""
Encryption helpers.
Key derivation: PBKDF2-HMAC-SHA256 (100 000 iterations) → 32-byte key.
Cipher: Fernet (AES-128-CBC + HMAC-SHA256) from the `cryptography` package.
"""
import os
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


# ── Key derivation ────────────────────────────────────────────────────────────

def derive_key(password: str, salt: bytes) -> bytes:
    """Return a 32-byte key derived from *password* and *salt*."""
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations=100_000,
        dklen=32,
    )
    return dk


def _fernet_from_key(raw_key: bytes) -> Fernet:
    """Wrap a 32-byte raw key in a Fernet instance."""
    # Fernet expects a URL-safe base64-encoded 32-byte key
    return Fernet(base64.urlsafe_b64encode(raw_key))


# ── Public helpers ────────────────────────────────────────────────────────────

SALT_LEN = 16  # bytes — exported so other modules can reference it


def encrypt(plaintext: bytes, password: str) -> tuple[bytes, bytes]:
    """
    Encrypt *plaintext* with *password*.

    Returns
    -------
    (ciphertext, salt)
        Both are raw bytes.  The caller is responsible for storing the salt
        alongside the ciphertext (the payload builder does this).
    """
    salt = os.urandom(SALT_LEN)
    key  = derive_key(password, salt)
    f    = _fernet_from_key(key)
    return f.encrypt(plaintext), salt


def decrypt(ciphertext: bytes, password: str, salt: bytes) -> bytes:
    """
    Decrypt *ciphertext*.

    Raises
    ------
    ValueError
        If the password is wrong or the token is malformed.
    """
    key = derive_key(password, salt)
    f   = _fernet_from_key(key)
    try:
        return f.decrypt(ciphertext)
    except InvalidToken as exc:
        raise ValueError("Decryption failed — wrong password or corrupted data.") from exc
