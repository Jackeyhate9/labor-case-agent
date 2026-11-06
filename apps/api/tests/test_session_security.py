from __future__ import annotations


def test_desktop_session_token_is_required_when_configured(client, monkeypatch):
    monkeypatch.setenv("APP_SESSION_TOKEN", "desktop-test-token")

    missing = client.get("/api/system/health")
    wrong = client.get(
        "/api/system/health",
        headers={"X-App-Session": "wrong-token"},
    )
    accepted = client.get(
        "/api/system/health",
        headers={"X-App-Session": "desktop-test-token"},
    )

    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "SESSION_REQUIRED"
    assert wrong.status_code == 401
    assert accepted.status_code == 200


def test_development_api_remains_available_without_configured_token(client, monkeypatch):
    monkeypatch.delenv("APP_SESSION_TOKEN", raising=False)

    response = client.get("/api/system/health")

    assert response.status_code == 200


def test_valid_header_establishes_http_only_session_cookie(client, monkeypatch):
    monkeypatch.setenv("APP_SESSION_TOKEN", "desktop-test-token")

    first = client.get(
        "/api/system/health",
        headers={"X-App-Session": "desktop-test-token"},
    )
    cookie = first.headers.get("set-cookie", "")
    follow_up = client.get(
        "/api/system/health",
        headers={"Referer": "http://127.0.0.1:3000/"},
    )
    foreign = client.get(
        "/api/system/health",
        headers={"Referer": "http://untrusted.local/"},
    )

    assert "app_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert follow_up.status_code == 200
    assert foreign.status_code == 403
