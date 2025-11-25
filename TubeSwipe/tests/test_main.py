from fastapi.testclient import TestClient
import pytest

def test_home_not_logged_in(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert "Login with Google" in response.text

def test_login_redirect(client: TestClient):
    response = client.get("/login", follow_redirects=False)
    assert response.status_code == 307
    assert "/auth/callback" in response.headers["location"]

def test_auth_callback_mock(client: TestClient):
    response = client.get("/auth/callback?mock=true", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/"
    
    # Verify session is set
    # Note: TestClient handles cookies/sessions automatically
    response = client.get("/")
    assert "Welcome" in response.text or "Logout" in response.text

def test_feed_unauthenticated(client: TestClient):
    # Clear cookies to ensure unauthenticated
    client.cookies.clear()
    response = client.get("/api/feed")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_feed_authenticated(client: TestClient):
    # Login first
    client.get("/auth/callback?mock=true")
    
    # Since the endpoint is async, TestClient handles it synchronously.
    # We don't strictly need 'await' here if using TestClient, 
    # but marking the test as async and using 'await' is good practice if we were using AsyncClient.
    # However, TestClient is synchronous.
    
    response = client.get("/api/feed")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "video_id" in data[0]

def test_swipe_action(client: TestClient):
    client.get("/auth/callback?mock=true")
    
    # Test Skip
    response = client.post("/api/swipe", json={"video_id": "123", "action": "skip"})
    assert response.status_code == 200
    assert response.json()["status"] == "skipped"

    # Test Save
    response = client.post("/api/swipe", json={"video_id": "123", "action": "save"})
    assert response.status_code == 200
    assert response.json()["status"] == "saved"
