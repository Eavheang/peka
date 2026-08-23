from uuid import UUID, uuid4

import pytest

from app.auth import routes, service
from app.auth.security import hash_password


def user(role="staff", password="correct password"):
    return {"id": uuid4(), "email": "user@example.com", "role": role,
            "password_hash": hash_password(password), "token_version": 0, "is_active": True}


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
    token = routes.create_access_token(str(account["id"]), account["role"], 0)
    account["token_version"] = 1
    monkeypatch.setattr(routes, "current_user", lambda user_id: account)
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_create_users_role_access_duplicate_and_logout(client, monkeypatch):
    staff = user()
    senior = user("senior")
    admin = user("admin")
    for account in (staff, senior):
        monkeypatch.setattr(routes, "current_user", lambda user_id, account=account: account)
        token = routes.create_access_token(str(account["id"]), account["role"], 0)
        assert client.post("/auth/users", headers={"Authorization": f"Bearer {token}"},
                           json={"email": "new@example.com", "password": "long enough password"}).status_code == 403
    monkeypatch.setattr(routes, "current_user", lambda user_id: admin)
    admin_token = routes.create_access_token(str(admin["id"]), "admin", 0)
    created = {"id": uuid4(), "email": "new@example.com", "role": "staff", "is_active": True}
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


def test_senior_cannot_use_admin_endpoints(client, monkeypatch):
    senior = user("senior")
    target = user()
    token = routes.create_access_token(str(senior["id"]), "senior", 0)
    monkeypatch.setattr(routes, "current_user", lambda user_id: senior)
    headers = {"Authorization": f"Bearer {token}"}

    assert client.post(
        "/auth/users", headers=headers,
        json={"email": "new@example.com", "password": "long enough password"},
    ).status_code == 403
    assert client.patch(
        f"/auth/users/{target['id']}", headers=headers, json={"is_active": False}
    ).status_code == 403
    assert client.delete(f"/auth/users/{target['id']}", headers=headers).status_code == 403


@pytest.mark.parametrize("role", ["staff", "senior", "admin"])
def test_admin_can_create_each_user_role(client, monkeypatch, role):
    admin = user("admin")
    token = routes.create_access_token(str(admin["id"]), "admin", 0)
    created = {"id": uuid4(), "email": f"{role}@example.com", "role": role, "is_active": True}
    captured = {}

    monkeypatch.setattr(routes, "current_user", lambda user_id: admin)
    monkeypatch.setattr(routes, "create_user", lambda data: captured.update(data=data) or created)

    response = client.post(
        "/auth/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": created["email"], "password": "long enough password", "role": role},
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": str(created["id"]), "email": created["email"], "role": role, "is_active": True
    }
    assert captured["data"].role == role


def test_inactive_user_cannot_login(monkeypatch):
    account = user(password="correct password")
    account["is_active"] = False
    monkeypatch.setattr(service.auth_repository, "find_by_email", lambda email: account)

    assert service.authenticate(account["email"], "correct password") is None


def test_admin_can_change_activation_and_delete_only_inactive(client, monkeypatch):
    admin = user("admin")
    target = user()
    accounts = {admin["id"]: admin, target["id"]: target}
    admin_token = routes.create_access_token(str(admin["id"]), "admin", 0)
    target_token = routes.create_access_token(str(target["id"]), "staff", 0)
    headers = {"Authorization": f"Bearer {admin_token}"}

    monkeypatch.setattr(routes, "current_user", lambda user_id: accounts.get(user_id))

    def set_active(user_id, is_active):
        account = accounts.get(user_id)
        if account is None:
            raise service.UserNotFoundError
        if account["is_active"] != is_active:
            account["token_version"] += 1
        account["is_active"] = is_active
        return account

    def delete(user_id):
        account = accounts.get(user_id)
        if account is None:
            raise service.UserNotFoundError
        if account["is_active"]:
            raise service.UserMustBeInactiveError
        del accounts[user_id]

    monkeypatch.setattr(routes, "set_user_active", set_active)
    monkeypatch.setattr(routes, "delete_user", delete)

    response = client.patch(
        f"/auth/users/{target['id']}", headers=headers, json={"is_active": False}
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert client.get(
        "/auth/me", headers={"Authorization": f"Bearer {target_token}"}
    ).status_code == 401

    response = client.patch(
        f"/auth/users/{target['id']}", headers=headers, json={"is_active": True}
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is True
    assert client.delete(f"/auth/users/{target['id']}", headers=headers).status_code == 409

    client.patch(f"/auth/users/{target['id']}", headers=headers, json={"is_active": False})
    assert client.delete(f"/auth/users/{target['id']}", headers=headers).status_code == 204
    assert client.delete(f"/auth/users/{target['id']}", headers=headers).status_code == 404
