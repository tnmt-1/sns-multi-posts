import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """
    FastAPI TestClient fixture.
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture
def mock_twitter_account():
    return {
        "id": "12345",
        "username": "testuser",
        "name": "Test User",
        "token": {"oauth_token": "mock_token", "oauth_token_secret": "mock_secret"},
    }
