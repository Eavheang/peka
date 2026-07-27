import pytest
from pydantic import SecretStr, ValidationError

from app.auth.security import create_access_token, decode_access_token, hash_password, verify_password
from app.config import Settings


def test_password_hash_and_jwt_round_trip() -> None:
    password_hash = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong", password_hash)

    token = create_access_token("00000000-0000-0000-0000-000000000001", "admin", 0)
    claims = decode_access_token(token)
    assert claims["sub"] == "00000000-0000-0000-0000-000000000001"
    assert claims["role"] == "admin"
    assert claims["ver"] == 0
    assert {"iss", "aud", "iat", "nbf", "exp", "jti"} <= claims.keys()


def test_jwt_rejects_tampering() -> None:
    token = create_access_token("00000000-0000-0000-0000-000000000001", "member", 0)
    parts = token.split(".")
    parts[-1] = ("a" if parts[-1][0] != "a" else "b") + parts[-1][1:]
    with pytest.raises(Exception):
        decode_access_token(".".join(parts))


def test_settings_normalize_admin_email() -> None:
    settings = Settings(
        jwt_secret_key=SecretStr("test-only-secret-that-is-at-least-32-chars"),
        admin_email=" Admin@Example.COM ",
        admin_password=SecretStr("bootstrap password"),
    )
    assert settings.admin_email == "admin@example.com"


def test_settings_validate_auth_configuration() -> None:
    secret = SecretStr("test-only-secret-that-is-at-least-32-chars")
    with pytest.raises(ValidationError):
        Settings(jwt_secret_key=SecretStr("short"))
    with pytest.raises(ValidationError):
        Settings(jwt_secret_key=secret, admin_email="admin@example.com", admin_password=None)
    with pytest.raises(ValidationError):
        Settings(jwt_secret_key=secret, jwt_access_token_expire_minutes=61)
    with pytest.raises(ValidationError):
        Settings(jwt_secret_key=SecretStr("replace-with-at-least-32-random-characters"))
