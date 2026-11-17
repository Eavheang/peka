import socket

import pytest
from fastapi.testclient import TestClient

from app import connectivity
from app.auth import mailer, service
from app.auth.routes import authenticated
from app.chat import service as chat_service
from app.engine.web_search import service as web_search_service
from app.main import app


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(connectivity, "_last_check", (float("inf"), False))
    monkeypatch.setattr(web_search_service, "provider_config", lambda: {"exa_api_key": "key"})
    app.dependency_overrides[authenticated] = lambda: {"id": "u1", "role": "admin"}
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_probe_result_is_cached(monkeypatch):
    calls = []

    def unreachable(*args, **kwargs):
        calls.append(args)
        raise OSError("Network is unreachable")

    monkeypatch.setattr(connectivity, "_last_check", (float("-inf"), True))
    monkeypatch.setattr(socket, "create_connection", unreachable)

    assert connectivity.is_online() is False
    assert connectivity.is_online() is False
    assert len(calls) == 1


def test_status_reports_offline_and_configured_features(offline):
    body = offline.get("/status").json()

    assert body["online"] is False
    assert body["configured"]["web_search"] is True


def test_chat_plans_from_documents_when_offline(offline, monkeypatch):
    monkeypatch.setattr(chat_service, "generate_structured", lambda *a, **k: pytest.fail("No model call offline"))

    plan = chat_service._search_plan("Any news today?", None, web_search=True)

    assert plan.tool == "search_knowledge_base"


def test_offline_skips_email_and_blocks_google_drive(offline, monkeypatch):
    monkeypatch.setattr(mailer, "mail_configured", lambda: True)
    monkeypatch.setattr(service, "mail_configured", lambda: True)
    monkeypatch.setattr(mailer.smtplib, "SMTP", lambda *a, **k: pytest.fail("SMTP must not be tried offline"))
    invitation = {"email": "a@b.co", "role": "staff"}

    result = service._deliver(invitation, "token", "http://app")

    assert result["email_sent"] is False and result["email_error"] == "offline"
    assert offline.get("/integrations/google/picker").status_code == 503
