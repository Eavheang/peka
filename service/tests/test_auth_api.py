from uuid import UUID, uuid4

import pytest

from app.auth import routes
from app.auth.security import hash_password


def user(role="member", password="correct password"):
    return {"id": uuid4(), "email": "user@example.com", "role": role,
            "password_hash": hash_password(password), "token_version": 0}


def test_login_and_me_assert_role_claim(client, monkeypatch):
    account = user("admin")
    monkeypatch.setattr(routes, "authenticate", lambda email, password: account)
    response = client.post("/auth/login", json={"email": account["email"], "password": "x"})
    assert response.status_code == 200
    claims = routes.decode_access_token(response.json()["access_token"])
    assert claims["role"] == "admin"
    monkeypatch.setattr(routes, "current_user", lambda user_id: account)
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"})
    assert me.status_code == 200 and me.json()["role"] == "admin"


@pytest.mark.parametrize(
    "credentials",
    [{"email": "unknown@example.com", "password": "wrong"},
     {"email": "user@example.com", "password": "wrong"}],
)
def test_login_rejects_unknown_and_wrong_credentials_generically(client, monkeypatch, credentials):
    monkeypatch.setattr(routes, "authenticate", lambda email, password: None)

    response = client.post("/auth/login", json=credentials)

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication credentials"}
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_auth_rejects_missing_invalid_and_version_mismatch(client, monkeypatch):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401
    account = user()
    token = routes.create_access_token(str(account["id"]), "member", 0)
    account["token_version"] = 1
    monkeypatch.setattr(routes, "current_user", lambda user_id: account)
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_create_users_role_access_duplicate_and_logout(client, monkeypatch):
    member = user()
    admin = user("admin")
    monkeypatch.setattr(routes, "current_user", lambda user_id: member)
    member_token = routes.create_access_token(str(member["id"]), "member", 0)
    assert client.post("/auth/users", headers={"Authorization": f"Bearer {member_token}"},
                       json={"email": "new@example.com", "password": "long enough password"}).status_code == 403
    monkeypatch.setattr(routes, "current_user", lambda user_id: admin)
    admin_token = routes.create_access_token(str(admin["id"]), "admin", 0)
    created = {"id": uuid4(), "email": "new@example.com", "role": "member"}
    monkeypatch.setattr(routes, "create_user", lambda data: created)
    response = client.post("/auth/users", headers={"Authorization": f"Bearer {admin_token}"},
                           json={"email": created["email"], "password": "long enough password"})
    assert response.status_code == 201
    monkeypatch.setattr(routes, "create_user", lambda data: (_ for _ in ()).throw(ValueError()))
    assert client.post("/auth/users", headers={"Authorization": f"Bearer {admin_token}"},
                       json={"email": "new@example.com", "password": "long enough password"}).status_code == 409
    revoked = {**admin, "token_version": 0}
    monkeypatch.setattr(routes, "current_user", lambda user_id: revoked)
    monkeypatch.setattr(routes.auth_repository, "revoke", lambda user_id: revoked.update(token_version=1))
    assert client.post("/auth/logout", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 204
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 401


@pytest.mark.parametrize("role", ["member", "admin"])
def test_admin_can_create_each_user_role(client, monkeypatch, role):
    admin = user("admin")
    token = routes.create_access_token(str(admin["id"]), "admin", 0)
    created = {"id": uuid4(), "email": f"{role}@example.com", "role": role}
    captured = {}

    monkeypatch.setattr(routes, "current_user", lambda user_id: admin)
    monkeypatch.setattr(routes, "create_user", lambda data: captured.update(data=data) or created)

    response = client.post(
        "/auth/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": created["email"], "password": "long enough password", "role": role},
    )

    assert response.status_code == 201
    assert response.json() == {"id": str(created["id"]), "email": created["email"], "role": role}
    assert captured["data"].role == role
