from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from pwdlib import PasswordHash

from app.config import settings

password_hash = PasswordHash.recommended()
dummy_password_hash = password_hash.hash("dummy-password-for-timing-only")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_access_token(subject: str, role: str, version: int) -> str:
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    return jwt.encode(
        {"sub": subject, "role": role, "ver": version, "iss": settings.jwt_issuer,
         "aud": settings.jwt_audience, "iat": now, "nbf": now, "exp": expiry, "jti": str(uuid4())},
        settings.jwt_secret_key.get_secret_value(), algorithm="HS256",
    )


def decode_access_token(token: str) -> dict:
    claims = jwt.decode(
        token, settings.jwt_secret_key.get_secret_value(), algorithms=["HS256"],
        issuer=settings.jwt_issuer, audience=settings.jwt_audience,
        options={"require": ["sub", "role", "ver", "iss", "aud", "iat", "nbf", "exp", "jti"]},
    )
    if not isinstance(claims["sub"], str) or claims["role"] not in {"member", "admin"} or type(claims["ver"]) is not int:
        raise jwt.InvalidTokenError("invalid token claims")
    return claims
