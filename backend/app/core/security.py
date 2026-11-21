"""Authentication, password hashing (scrypt), and RFC 7519 HS256 JWT utilities."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.core.exceptions import UnauthorizedError


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using salted scrypt."""
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        plain_password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return f"scrypt${_b64url_encode(salt)}${_b64url_encode(derived)}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored scrypt hash."""
    try:
        scheme, salt_b64, hash_b64 = hashed_password.split("$", 2)
        if scheme != "scrypt":
            return False
        salt = _b64url_decode(salt_b64)
        expected = _b64url_decode(hash_b64)
        derived = hashlib.scrypt(
            plain_password.encode("utf-8"),
            salt=salt,
            n=2**14,
            r=8,
            p=1,
            dklen=len(expected),
        )
        return hmac.compare_digest(derived, expected)
    except Exception:
        return False


def _encode_jwt(payload: dict[str, Any]) -> str:
    header = {"alg": settings.JWT_ALGORITHM, "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"


def create_access_token(*, user_id: UUID, organization_id: UUID, role: str) -> tuple[str, int]:
    """Issue a signed HS256 JWT access token and return (token, expires_in_seconds)."""
    now = datetime.now(UTC)
    expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    exp = now + expires_delta
    payload = {
        "sub": str(user_id),
        "org_id": str(organization_id),
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return _encode_jwt(payload), int(expires_delta.total_seconds())


def create_refresh_token(*, user_id: UUID, organization_id: UUID, role: str) -> str:
    """Issue a signed HS256 JWT refresh token."""
    now = datetime.now(UTC)
    exp = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "org_id": str(organization_id),
        "role": role,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return _encode_jwt(payload)


def decode_token(token: str, *, expected_type: str = "access") -> dict[str, Any]:
    """Verify HS256 JWT signature, expiration, and token type."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise UnauthorizedError("Malformed bearer token.")
        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected_sig = hmac.new(
            settings.JWT_SECRET_KEY.encode("utf-8"),
            signing_input,
            hashlib.sha256,
        ).digest()
        provided_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, provided_sig):
            raise UnauthorizedError("Invalid token signature.")

        payload: dict[str, Any] = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except UnauthorizedError:
        raise
    except Exception as exc:
        raise UnauthorizedError("Invalid authentication token.") from exc

    if payload.get("type") != expected_type:
        raise UnauthorizedError(f"Expected {expected_type} token.")

    exp = payload.get("exp")
    if not isinstance(exp, int) or datetime.now(UTC).timestamp() >= exp:
        raise UnauthorizedError("Authentication token has expired.")

    if not payload.get("sub") or not payload.get("org_id"):
        raise UnauthorizedError("Token missing required subject or tenant claims.")

    return payload
