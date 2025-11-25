import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

@pytest.fixture
def client():
    # Force mock mode for tests
    settings.MOCK_MODE = True
    with TestClient(app) as c:
        yield c

@pytest.fixture
def mock_youtube_client():
    # Return a mock object if needed for direct service testing
    class MockYouTube:
        pass
    return MockYouTube()
