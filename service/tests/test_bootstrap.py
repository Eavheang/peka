import asyncio
from types import SimpleNamespace

from pydantic import SecretStr

from app import main
from app.auth import repository
from app.auth.security import verify_password


def test_lifespan_bootstraps_normalized_hashed_admin(monkeypatch):
    calls = []
    monkeypatch.setattr(
        main,
        "settings",
        SimpleNamespace(
            admin_email=" Admin@Example.COM ",
            admin_password=SecretStr("bootstrap password"),
        ),
    )
    monkeypatch.setattr(
        main.auth_repository,
        "bootstrap_admin",
        lambda email, password_hash: calls.append((email, password_hash)),
    )

    async def run_lifespan():
        async with main.lifespan(main.app):
            pass

    asyncio.run(run_lifespan())

    assert calls[0][0] == "admin@example.com"
    assert calls[0][1] != "bootstrap password"
    assert verify_password("bootstrap password", calls[0][1])


def test_bootstrap_admin_does_not_insert_when_admin_exists(monkeypatch):
    class Result:
        def fetchone(self):
            return {"?column?": 1}

    class Connection:
        def __init__(self):
            self.queries = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, query, params=None):
            self.queries.append((query, params))
            return Result()

    connection = Connection()
    monkeypatch.setattr(repository, "get_connection", lambda: connection)

    repository.auth_repository.bootstrap_admin("admin@example.com", "hashed password")

    assert not any(query.startswith("INSERT") for query, _ in connection.queries)
