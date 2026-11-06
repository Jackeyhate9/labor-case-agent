from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


def envelope(response, status=200):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"success", "data", "error", "meta"}
    assert body["success"] is True
    return body["data"]


def test_llm_config_get_is_write_only_for_secrets(client, monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_CONFIG_FILE", str(tmp_path / "llm-config.json"))
    monkeypatch.setenv("LLM_SECRET_FILE", str(tmp_path / "llm-secret.bin"))
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    data = envelope(client.get("/api/system/llm-config"))

    assert data["base_url"] == ""
    assert data["model"] == ""
    assert data["api_key_configured"] is False
    assert data["returned"] is False
    assert "api_key" not in data


def test_llm_config_patch_persists_only_non_secret_fields(client, monkeypatch, tmp_path):
    config_file = tmp_path / "llm-config.json"
    secret_file = tmp_path / "llm-secret.bin"
    monkeypatch.setenv("LLM_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("LLM_SECRET_FILE", str(secret_file))
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    data = envelope(
        client.patch(
            "/api/system/llm-config",
            json={"base_url": "https://api.example.test/v1/", "model": "example-chat"},
        )
    )

    assert data["base_url"] == "https://api.example.test/v1"
    assert data["model"] == "example-chat"
    assert data["api_key_configured"] is False
    assert json.loads(config_file.read_text(encoding="utf-8")) == {
        "base_url": "https://api.example.test/v1",
        "model": "example-chat",
    }
    assert not secret_file.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI is the supported persistent secret store")
def test_llm_config_patch_encrypts_api_key_with_current_windows_user(client, monkeypatch, tmp_path):
    config_file = tmp_path / "llm-config.json"
    secret_file = tmp_path / "llm-secret.bin"
    monkeypatch.setenv("LLM_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("LLM_SECRET_FILE", str(secret_file))
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    secret = "sk-test-secret-that-must-be-encrypted"

    data = envelope(
        client.patch(
            "/api/system/llm-config",
            json={
                "base_url": "https://api.example.test/v1",
                "model": "example-chat",
                "api_key": secret,
            },
        )
    )

    assert data["api_key_configured"] is True
    assert data["storage"] == "windows_dpapi"
    assert data["returned"] is False
    assert secret not in json.dumps(data)
    assert secret.encode() not in secret_file.read_bytes()
    assert secret not in config_file.read_text(encoding="utf-8")
    assert "api_key" not in envelope(client.get("/api/system/llm-config"))


@pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI is the supported persistent secret store")
def test_llm_connection_test_reuses_saved_key_without_returning_it(client, monkeypatch, tmp_path):
    requests = []

    class ModelsHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append({"path": self.path, "authorization": self.headers.get("Authorization")})
            payload = json.dumps({"data": [{"id": "example-chat"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), ModelsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("SYSTEM_SETTINGS_FILE", str(tmp_path / "system-settings.json"))
        monkeypatch.setenv("LLM_CONFIG_FILE", str(tmp_path / "llm-config.json"))
        monkeypatch.setenv("LLM_SECRET_FILE", str(tmp_path / "llm-secret.bin"))
        monkeypatch.delenv("LLM_BASE_URL", raising=False)
        monkeypatch.delenv("LLM_MODEL", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        secret = "sk-saved-dpapi-key"
        base_url = f"http://127.0.0.1:{server.server_port}/v1"
        envelope(
            client.patch(
                "/api/system/settings",
                json={"offline_mode": False, "llm_provider": "openai-compatible"},
            )
        )
        envelope(
            client.patch(
                "/api/system/llm-config",
                json={"base_url": base_url, "model": "example-chat", "api_key": secret},
            )
        )
        monkeypatch.delenv("LLM_API_KEY", raising=False)

        data = envelope(client.post("/api/system/llm-config/test", json={}))

        assert data["ok"] is True
        assert data["provider"] == "openai-compatible"
        assert data["base_url"] == base_url
        assert data["model"] == "example-chat"
        assert data["model_available"] is True
        assert isinstance(data["latency_ms"], int)
        assert secret not in json.dumps(data)
        assert requests == [{"path": "/v1/models", "authorization": f"Bearer {secret}"}]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI is the supported persistent secret store")
def test_llm_config_can_explicitly_clear_the_saved_api_key(client, monkeypatch, tmp_path):
    secret_file = tmp_path / "llm-secret.bin"
    monkeypatch.setenv("LLM_CONFIG_FILE", str(tmp_path / "llm-config.json"))
    monkeypatch.setenv("LLM_SECRET_FILE", str(secret_file))
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    envelope(client.patch("/api/system/llm-config", json={"api_key": "sk-delete-me"}))
    assert secret_file.is_file()

    data = envelope(client.patch("/api/system/llm-config", json={"clear_api_key": True}))

    assert data["api_key_configured"] is False
    assert not secret_file.exists()
    assert "LLM_API_KEY" not in os.environ


def test_llm_config_rejects_setting_and_clearing_key_in_one_request(client, monkeypatch, tmp_path):
    secret_file = tmp_path / "llm-secret.bin"
    monkeypatch.setenv("LLM_CONFIG_FILE", str(tmp_path / "llm-config.json"))
    monkeypatch.setenv("LLM_SECRET_FILE", str(secret_file))
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    response = client.patch(
        "/api/system/llm-config",
        json={"api_key": "sk-ambiguous", "clear_api_key": True},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "sk-ambiguous" not in response.text
    assert not secret_file.exists()
