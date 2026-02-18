"""Password hashing and JWT token management."""

from datetime import datetime, timedelta, timezone

import hashlib
import hmac
import json
import base64
import secrets

from shieldops.config import settings


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${dk.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a PBKDF2 hash."""
    try:
        salt, hash_hex = hashed_password.split("$", 1)
        dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode(), salt.encode(), 100_000)
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def create_access_token(
    subject: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token using HMAC-SHA256."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_expire_minutes)
    )
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": subject,
        "role": role,
        "exp": int(expire.timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    header_b64 = _b64url_encode(json.dumps(header).encode())
    payload_b64 = _b64url_encode(json.dumps(payload).encode())
    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        settings.jwt_secret_key.encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    sig_b64 = _b64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_token(token: str) -> dict | None:
    """Decode and verify a JWT token. Returns payload dict or None."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(
            settings.jwt_secret_key.encode(), signing_input.encode(), hashlib.sha256
        ).digest()
        actual_sig = _b64url_decode(sig_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        payload = json.loads(_b64url_decode(payload_b64))

        # Check expiration
        exp = payload.get("exp")
        if exp and datetime.now(timezone.utc).timestamp() > exp:
            return None

        return payload
    except Exception:
        return None
