import psycopg
import pytest

from app.auth import repository


class Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, results=None, error=None):
        self.queries = []
        self.results = results or {}
        self.error = error

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        self.queries.append((query, params))
        if self.error is not None and query.startswith("INSERT"):
            raise self.error
        for prefix, result in self.results.items():
            if query.startswith(prefix):
                return Result(result)
        return Result()


def test_find_by_email_compares_lowercased_email(monkeypatch):
    connection = Connection()
    monkeypatch.setattr(repository, "get_connection", lambda: connection)

    repository.auth_repository.find_by_email("User@Example.com")

    query, params = connection.queries[0]
    assert "lower(email) = lower(%s)" in query
    assert params == ("User@Example.com",)
