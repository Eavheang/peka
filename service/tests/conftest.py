from collections.abc import Iterator
import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-that-is-at-least-32-chars")
os.environ.setdefault("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("LLM_BASE_URL", "http://localhost:8080/v1")
os.environ.setdefault("LLM_API_KEY", "test-only-key")
os.environ.setdefault("LLM_MODEL", "test-model")

from app.main import app


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
