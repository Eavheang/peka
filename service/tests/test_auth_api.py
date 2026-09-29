from uuid import uuid4

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


def test_users_can_only_be_added_through_invitations(client, monkeypatch):
    admin = user("admin")
    monkeypatch.setattr(routes, "current_user", lambda user_id: admin)
    token = routes.create_access_token(str(admin["id"]), "admin", 0)

    response = client.post("/auth/users", headers={"Authorization": f"Bearer {token}"},
                           json={"email": "new@example.com", "password": "long enough password"})

    assert response.status_code == 405


def test_logout_revokes_the_token(client, monkeypatch):
    admin = user("admin")
    admin_token = routes.create_access_token(str(admin["id"]), "admin", 0)
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
        "/auth/invitations", headers=headers, json={"email": "new@example.com"}
    ).status_code == 403
    assert client.patch(
        f"/auth/users/{target['id']}", headers=headers, json={"is_active": False}
    ).status_code == 403
    assert client.delete(f"/auth/users/{target['id']}", headers=headers).status_code == 403


def test_admin_can_change_role_and_cannot_demote_self(client, monkeypatch):
    admin = user("admin")
    target = user("staff")
    token = routes.create_access_token(str(admin["id"]), "admin", 0)
    monkeypatch.setattr(routes, "current_user", lambda user_id: admin)
    changed = {**target, "role": "senior", "display_name": ""}
    monkeypatch.setattr(routes, "set_user_role", lambda user_id, role, actor_id: changed)

    response = client.patch(
        f"/auth/users/{target['id']}/role",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "senior"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "senior"

    monkeypatch.setattr(
        routes,
        "set_user_role",
        lambda user_id, role, actor_id: (_ for _ in ()).throw(service.CannotChangeOwnAdminRoleError()),
    )
    response = client.patch(
        f"/auth/users/{admin['id']}/role",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "staff"},
    )
    assert response.status_code == 409


def test_user_can_change_name_and_password(client, monkeypatch):
    account = user("staff")
    token = routes.create_access_token(str(account["id"]), account["role"], 0)
    headers = {"Authorization": f"Bearer {token}"}
    monkeypatch.setattr(routes, "current_user", lambda user_id: account)
    monkeypatch.setattr(
        routes,
        "set_display_name",
        lambda user_id, display_name: {**account, "display_name": display_name},
    )
    profile = client.patch("/auth/me", headers=headers, json={"display_name": "  Ada  "})
    assert profile.status_code == 200
    assert profile.json()["display_name"] == "Ada"

    changed = {}
    monkeypatch.setattr(
        routes,
        "change_password",
        lambda user_id, current_password, new_password: changed.update(
            user_id=user_id, current=current_password, new=new_password
        ),
    )
    response = client.post(
        "/auth/password",
        headers=headers,
        json={"current_password": "old password", "new_password": "new password long"},
    )
    assert response.status_code == 204
    assert changed["current"] == "old password"
    assert changed["new"] == "new password long"


def test_password_change_rejects_wrong_current_password(client, monkeypatch):
    account = user()
    token = routes.create_access_token(str(account["id"]), account["role"], 0)
    monkeypatch.setattr(routes, "current_user", lambda user_id: account)
    monkeypatch.setattr(
        routes,
        "change_password",
        lambda *args: (_ for _ in ()).throw(service.IncorrectCurrentPasswordError()),
    )

    response = client.post(
        "/auth/password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "wrong", "new_password": "new password long"},
    )
    assert response.status_code == 400


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
