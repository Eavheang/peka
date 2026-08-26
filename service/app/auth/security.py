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


def _create_token(subject: str, role: str, version: int, token_type: str, minutes: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": subject, "role": role, "ver": version, "typ": token_type, "iss": settings.jwt_issuer,
         "aud": settings.jwt_audience, "iat": now, "nbf": now,
         "exp": now + timedelta(minutes=minutes), "jti": str(uuid4())},
        settings.jwt_secret_key.get_secret_value(), algorithm="HS256",
    )


def create_access_token(subject: str, role: str, version: int) -> str:
    return _create_token(subject, role, version, "access", settings.jwt_access_token_expire_minutes)


def create_refresh_token(subject: str, role: str, version: int) -> str:
    return _create_token(subject, role, version, "refresh", settings.jwt_refresh_token_expire_days * 24 * 60)


def decode_access_token(token: str) -> dict:
    claims = jwt.decode(token, settings.jwt_secret_key.get_secret_value(), algorithms=["HS256"], issuer=settings.jwt_issuer, audience=settings.jwt_audience,
                        options={"require": ["sub", "role", "ver", "typ", "iss", "aud", "iat", "nbf", "exp", "jti"]})
    if claims.get("typ") != "access" or not isinstance(claims["sub"], str) or not isinstance(claims["role"], str) or claims["role"] not in {"admin", "senior", "staff"} or type(claims["ver"]) is not int:
        raise jwt.InvalidTokenError("invalid token claims")
    return claims


def decode_refresh_token(token: str) -> dict:
    claims = jwt.decode(token, settings.jwt_secret_key.get_secret_value(), algorithms=["HS256"], issuer=settings.jwt_issuer, audience=settings.jwt_audience,
                        options={"require": ["sub", "role", "ver", "typ", "iss", "aud", "iat", "nbf", "exp", "jti"]})
    if claims.get("typ") != "refresh" or not isinstance(claims["sub"], str) or claims["role"] not in {"admin", "senior", "staff"} or type(claims["ver"]) is not int:
        raise jwt.InvalidTokenError("invalid refresh token claims")
    return claims
