from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.auth import mailer, routes, service
from app.auth.security import decode_access_token
from app.config import settings

NOW = datetime.now(timezone.utc)


def admin_headers(monkeypatch, role="admin"):
    account = {"id": uuid4(), "email": "admin@example.com", "role": role,
               "token_version": 0, "is_active": True}
    monkeypatch.setattr(routes, "current_user", lambda user_id: account)
    return {"Authorization": f"Bearer {routes.create_access_token(str(account['id']), role, 0)}"}


def invitation(email="new@example.com", role="staff"):
    return {"id": uuid4(), "email": email, "role": role, "expires_at": NOW, "created_at": NOW}


@pytest.mark.parametrize("role", ["staff", "senior"])
def test_only_admins_manage_invitations(client, monkeypatch, role):
    headers = admin_headers(monkeypatch, role)
    target = uuid4()

    assert client.post("/auth/invitations", headers=headers, json={"email": "a@b.co"}).status_code == 403
    assert client.get("/auth/invitations", headers=headers).status_code == 403
    assert client.post(f"/auth/invitations/{target}/resend", headers=headers).status_code == 403
    assert client.delete(f"/auth/invitations/{target}", headers=headers).status_code == 403


def test_admin_invites_user_and_gets_link(client, monkeypatch):
    headers = admin_headers(monkeypatch)
    captured = {}

    def fake_invite(email, role, invited_by, base_url=None):
        captured.update(email=email, role=role)
        return {**invitation(email, role), "invite_url": "http://app/accept-invite?token=t", "email_sent": True}

    monkeypatch.setattr(routes, "invite_user", fake_invite)

    response = client.post("/auth/invitations", headers=headers, json={"email": " New@Example.com ", "role": "senior"})

    assert response.status_code == 201
    assert captured == {"email": "new@example.com", "role": "senior"}
    assert response.json()["invite_url"] == "http://app/accept-invite?token=t"
    assert response.json()["email_sent"] is True


@pytest.mark.parametrize(
    "origin, expected",
    [
        ("https://abc.ngrok-free.dev", "https://abc.ngrok-free.dev"),
        ("http://localhost:3000", "http://localhost:3000"),
        (None, None),
        ("null", None),
        ("javascript://evil", None),
        ("https://abc.ngrok-free.dev/path", None),
        ("ftp://host", None),
    ],
)
def test_invite_link_uses_the_browser_origin_when_valid(client, monkeypatch, origin, expected):
    headers = admin_headers(monkeypatch)
    seen = {}
    monkeypatch.setattr(
        routes, "invite_user",
        lambda email, role, invited_by, base_url=None: seen.update(base_url=base_url) or {
            **invitation(email, role), "invite_url": "u", "email_sent": False,
        },
    )
    if origin is not None:
        headers["Origin"] = origin

    assert client.post("/auth/invitations", headers=headers, json={"email": "a@b.co"}).status_code == 201
    assert seen["base_url"] == expected


def test_resend_uses_the_browser_origin(client, monkeypatch):
    headers = {**admin_headers(monkeypatch), "Origin": "https://abc.ngrok-free.dev"}
    seen = {}
    monkeypatch.setattr(
        routes, "resend_invitation",
        lambda id, base_url=None: seen.update(base_url=base_url) or {
            **invitation(), "invite_url": "u", "email_sent": False,
        },
    )

    assert client.post(f"/auth/invitations/{uuid4()}/resend", headers=headers).status_code == 200
    assert seen["base_url"] == "https://abc.ngrok-free.dev"


def test_deliver_prefers_the_given_base_url_over_the_configured_one(monkeypatch):
    monkeypatch.setattr(service, "send_invitation", lambda *args: False)
    monkeypatch.setattr(settings, "app_base_url", "http://configured:3000/")
    item = invitation()

    assert service._deliver(item, "T", "https://abc.ngrok-free.dev")["invite_url"] == (
        "https://abc.ngrok-free.dev/accept-invite?token=T"
    )
    assert service._deliver(item, "T", None)["invite_url"] == "http://configured:3000/accept-invite?token=T"


@pytest.mark.parametrize(
    "error, message",
    [(service.EmailAlreadyRegisteredError, "already exists"), (service.InvitationPendingError, "pending invitation")],
)
def test_invite_conflicts(client, monkeypatch, error, message):
    headers = admin_headers(monkeypatch)
    monkeypatch.setattr(routes, "invite_user", lambda *args: (_ for _ in ()).throw(error()))

    response = client.post("/auth/invitations", headers=headers, json={"email": "a@b.co"})

    assert response.status_code == 409
    assert message in response.json()["detail"]


def test_invite_rejects_invalid_email_and_role(client, monkeypatch):
    headers = admin_headers(monkeypatch)

    assert client.post("/auth/invitations", headers=headers, json={"email": "nope"}).status_code == 422
    assert client.post("/auth/invitations", headers=headers, json={"email": "a@b.co", "role": "root"}).status_code == 422


def test_invite_user_stores_only_a_token_hash_and_builds_the_link(monkeypatch):
    stored = {}
    sent = {}
    monkeypatch.setattr(service.auth_repository, "find_by_email", lambda email: None)
    monkeypatch.setattr(
        service.invitation_repository, "create",
        lambda email, role, token_hash, invited_by, expires_at: stored.update(token_hash=token_hash) or invitation(email, role),
    )
    monkeypatch.setattr(
        service, "send_invitation", lambda to, url, days, role: sent.update(to=to, url=url) or True
    )
    monkeypatch.setattr(settings, "app_base_url", "https://peka.example/")

    result = service.invite_user("new@example.com", "staff", uuid4())

    token = result["invite_url"].split("token=")[1]
    assert result["invite_url"].startswith("https://peka.example/accept-invite?token=")
    assert stored["token_hash"] == service._hash_token(token) != token
    assert result["email_sent"] is True and sent["to"] == "new@example.com"


def test_invite_user_rejects_existing_user_before_creating(monkeypatch):
    monkeypatch.setattr(service.auth_repository, "find_by_email", lambda email: {"id": uuid4()})
    monkeypatch.setattr(
        service.invitation_repository, "create", lambda *args: pytest.fail("must not create an invitation")
    )

    with pytest.raises(service.EmailAlreadyRegisteredError):
        service.invite_user("taken@example.com", "staff", uuid4())


def test_lookup_hides_whether_a_token_ever_existed(client, monkeypatch):
    monkeypatch.setattr(
        service.invitation_repository, "find_valid", lambda token_hash: None
    )

    response = client.post("/auth/invitations/lookup", json={"token": "bogus"})

    assert response.status_code == 404
    assert response.json() == {"detail": "This invitation is invalid or has expired"}


def test_lookup_returns_email_and_role(client, monkeypatch):
    monkeypatch.setattr(
        service.invitation_repository, "find_valid",
        lambda token_hash: {"email": "new@example.com", "role": "senior"},
    )

    response = client.post("/auth/invitations/lookup", json={"token": "abc"})

    assert response.status_code == 200
    assert response.json() == {"email": "new@example.com", "role": "senior"}


def test_accept_creates_account_and_signs_in(client, monkeypatch):
    user = {"id": uuid4(), "email": "new@example.com", "display_name": "Dara", "role": "senior",
            "token_version": 0, "is_active": True}
    seen = {}

    def fake_accept(token_hash, display_name, password_hash):
        seen.update(token_hash=token_hash, display_name=display_name, password_hash=password_hash)
        return user

    monkeypatch.setattr(service.invitation_repository, "accept", fake_accept)

    response = client.post(
        "/auth/invitations/accept",
        json={"token": "abc", "display_name": "  Dara ", "password": "a long enough password"},
    )

    assert response.status_code == 200
    claims = decode_access_token(response.json()["access_token"])
    assert claims["sub"] == str(user["id"]) and claims["role"] == "senior"
    assert seen["display_name"] == "Dara"
    assert seen["token_hash"] == service._hash_token("abc")
    assert seen["password_hash"] != "a long enough password"


def test_accept_rejects_bad_token_short_password_and_email_race(client, monkeypatch):
    payload = {"token": "abc", "display_name": "Dara", "password": "a long enough password"}

    monkeypatch.setattr(service.invitation_repository, "accept", lambda *args: None)
    assert client.post("/auth/invitations/accept", json=payload).status_code == 404

    monkeypatch.setattr(service.invitation_repository, "accept", lambda *args: (_ for _ in ()).throw(ValueError()))
    assert client.post("/auth/invitations/accept", json=payload).status_code == 409

    assert client.post("/auth/invitations/accept", json={**payload, "password": "short"}).status_code == 422
    assert client.post("/auth/invitations/accept", json={**payload, "display_name": "  "}).status_code == 422


def test_resend_and_revoke(client, monkeypatch):
    headers = admin_headers(monkeypatch)
    invitation_id = uuid4()
    monkeypatch.setattr(
        routes, "resend_invitation",
        lambda id, base_url=None: {
            **invitation(), "invite_url": "http://app/accept-invite?token=new", "email_sent": False,
        },
    )
    monkeypatch.setattr(routes, "revoke_invitation", lambda id: None)

    resent = client.post(f"/auth/invitations/{invitation_id}/resend", headers=headers)
    assert resent.status_code == 200 and resent.json()["email_sent"] is False
    assert client.delete(f"/auth/invitations/{invitation_id}", headers=headers).status_code == 204

    monkeypatch.setattr(routes, "revoke_invitation", lambda id: (_ for _ in ()).throw(service.InvitationNotFoundError()))
    assert client.delete(f"/auth/invitations/{invitation_id}", headers=headers).status_code == 404


class FakeSMTP:
    instances: list["FakeSMTP"] = []

    def __init__(self, host, port, timeout):
        self.host, self.port, self.messages, self.tls, self.login_args = host, port, [], False, None
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self):
        self.tls = True

    def login(self, user, password):
        self.login_args = (user, password)

    def send_message(self, message):
        self.messages.append(message)


def configure_smtp(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(settings, "smtp_host", "smtp.gmail.com")
    monkeypatch.setattr(settings, "smtp_user", "sender@gmail.com")
    monkeypatch.setattr(settings, "smtp_password", type(settings.llm_api_key)("app-password"))
    monkeypatch.setattr(settings, "smtp_from", None)


def test_mailer_sends_link_over_starttls(monkeypatch):
    configure_smtp(monkeypatch)

    assert mailer.send_invitation("dara@example.com", "http://app/accept-invite?token=t", 7, "senior") is True

    server = FakeSMTP.instances[0]
    assert (server.host, server.port, server.tls) == ("smtp.gmail.com", 587, True)
    assert server.login_args == ("sender@gmail.com", "app-password")
    message = server.messages[0]
    assert message["To"] == "dara@example.com" and message["From"] == "sender@gmail.com"
    plain = message.get_body(preferencelist=("plain",)).get_content()
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "http://app/accept-invite?token=t" in plain and "senior" in plain
    assert 'href="http://app/accept-invite?token=t"' in html
    assert "Senior" in html and "expires in 7 days" in html
    assert "#e96243" in html  # the app's primary colour on the button


def test_invitation_html_escapes_untrusted_values():
    html = mailer._invitation_html('http://x/?a=1&b="2"', 7, "<b>staff</b>")

    assert '&amp;b=&quot;2&quot;' in html
    assert "<B>" not in html and "&lt;B&gt;Staff&lt;/B&gt;" in html


def test_mailer_skips_when_unconfigured_and_survives_failures(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", None)
    assert mailer.send_invitation("dara@example.com", "http://x", 7, "staff") is False

    configure_smtp(monkeypatch)

    def refuse(*args, **kwargs):
        raise OSError("network down")

    monkeypatch.setattr(mailer.smtplib, "SMTP", refuse)
    assert mailer.send_invitation("dara@example.com", "http://x", 7, "staff") is False
