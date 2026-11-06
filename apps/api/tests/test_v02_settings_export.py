from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest


def envelope(response, status=200):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"success", "data", "error", "meta"}
    assert body["success"] is True
    return body


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("SYSTEM_SETTINGS_FILE", str(tmp_path / "system-settings.json"))
    monkeypatch.setenv("OCR_PROVIDER", "auto")
    monkeypatch.setenv("AUDIO_PROVIDER", "disabled")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "disabled")
    monkeypatch.setenv("LLM_PROVIDER", "disabled")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)


def test_settings_defaults_are_offline_and_secret_free(client):
    data = envelope(client.get("/api/system/settings"))["data"]
    assert data["offline_mode"] is True
    assert data["llm_provider"] == "disabled"
    assert data["secrets"] == {"storage": "environment_only", "returned": False}
    assert "api_key" not in json.dumps(data).lower().replace("api_key_configured", "")


def test_settings_patch_persists_across_clients(client, tmp_path):
    saved = envelope(client.patch("/api/system/settings", json={"offline_mode": False, "llm_provider": "ollama"}))["data"]
    assert saved["offline_mode"] is False and saved["llm_provider"] == "ollama"
    persisted = json.loads((tmp_path / "system-settings.json").read_text(encoding="utf-8"))
    assert persisted == {"offline_mode": False, "ocr_provider": "auto", "audio_provider": "disabled", "embedding_provider": "disabled", "llm_provider": "ollama"}
    assert envelope(client.get("/api/system/settings"))["data"]["llm_provider"] == "ollama"


@pytest.mark.parametrize(
    ("field", "value", "provider_key"),
    [
        ("ocr_provider", "auto", "ocr"),
        ("ocr_provider", "rapidocr", "ocr"),
        ("ocr_provider", "disabled", "ocr"),
        ("audio_provider", "moss-transcribe-diarize", "audio"),
        ("audio_provider", "disabled", "audio"),
        ("embedding_provider", "bge-m3", "embedding"),
        ("embedding_provider", "nemotron-3-embed-1b", "embedding"),
        ("embedding_provider", "disabled", "embedding"),
        ("llm_provider", "ollama", "llm"),
    ],
)
def test_each_local_provider_selection_is_persisted_and_reports_status(client, field, value, provider_key):
    data = envelope(client.patch("/api/system/settings", json={field: value}))["data"]
    assert data[field] == value
    status = data["providers"][provider_key]
    assert status["selected"] == value
    assert status["status"] in {"available", "unavailable", "disabled", "runtime_not_installed", "model_not_installed", "model_weights_incomplete", "not_configured"}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ocr_provider", "cloud-ocr"),
        ("audio_provider", "whisper-cloud"),
        ("embedding_provider", "unknown-vectorizer"),
        ("llm_provider", "mystery-model"),
    ],
)
def test_settings_reject_unknown_provider_values(client, tmp_path, field, value):
    response = client.patch("/api/system/settings", json={field: value})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert not (tmp_path / "system-settings.json").exists()


@pytest.mark.parametrize("secret_field", ["api_key", "llm_api_key", "openai_api_key", "provider_secret"])
def test_settings_api_rejects_secret_material(client, tmp_path, secret_field):
    response = client.patch("/api/system/settings", json={secret_field: "sk-must-not-persist"})
    assert response.status_code == 422
    assert "sk-must-not-persist" not in response.text
    assert not (tmp_path / "system-settings.json").exists()


@pytest.mark.parametrize("provider", ["openai-compatible", "deepseek-compatible", "qwen-compatible"])
def test_offline_mode_blocks_cloud_llm_effective_provider(client, provider):
    data = envelope(client.patch("/api/system/settings", json={"offline_mode": True, "llm_provider": provider}))["data"]
    llm = data["providers"]["llm"]
    assert llm["selected"] == provider
    assert llm["effective"] == "disabled"
    assert llm["enabled"] is False and llm["status"] == "blocked_by_offline_mode"


def test_online_cloud_llm_reports_configuration_without_returning_key(client, monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("LLM_API_KEY", "sk-private-value")
    data = envelope(client.patch("/api/system/settings", json={"offline_mode": False, "llm_provider": "openai-compatible"}))["data"]
    assert data["providers"]["llm"]["status"] == "configured"
    assert data["providers"]["llm"]["api_key_configured"] is True
    assert "sk-private-value" not in json.dumps(data)


def test_corrupted_persisted_settings_fail_explicitly(client, tmp_path):
    (tmp_path / "system-settings.json").write_text("{not-json", encoding="utf-8")
    response = client.get("/api/system/settings")
    assert response.status_code == 500
    assert response.json()["error"] == {"code": "SETTINGS_CORRUPTED", "message": "Persisted system settings are invalid"}


def test_settings_atomic_write_leaves_no_temporary_file(client, tmp_path):
    envelope(client.patch("/api/system/settings", json={"ocr_provider": "rapidocr"}))
    assert (tmp_path / "system-settings.json").is_file()
    assert not (tmp_path / "system-settings.json.tmp").exists()


def test_legacy_providers_endpoint_matches_persisted_settings(client):
    envelope(client.patch("/api/system/settings", json={"ocr_provider": "disabled", "embedding_provider": "bge-m3", "audio_provider": "moss-transcribe-diarize"}))
    providers = envelope(client.get("/api/system/providers"))["data"]
    assert providers["offline_mode"] is True
    assert providers["ocr"]["provider"] == "disabled" and providers["ocr"]["available"] is False
    assert providers["embedding"]["provider"] == "bge-m3"
    assert providers["audio"]["provider"] == "moss-transcribe-diarize"
    assert providers["llm"]["fabricates_fallback"] is False


def create_export_fixture(client):
    case = envelope(client.post("/api/cases", json={"title": "v0.2 export compatibility"}), 201)["data"]
    envelope(client.post(f"/api/cases/{case['id']}/wages", json={"period": "2026-01", "expected_amount": "6000.10", "paid_amount": "1000.05"}), 201)
    document = envelope(client.post(f"/api/cases/{case['id']}/documents/generate", json={"document_type": "arbitration_application"}), 201)["data"]
    return case, document


@pytest.mark.parametrize("fmt", ["json", "csv", "xlsx", "zip"])
def test_v02_case_export_preserves_v01_formats(client, fmt):
    case, _ = create_export_fixture(client)
    exported = envelope(client.post(f"/api/cases/{case['id']}/export", json={"format": fmt}))["data"]
    path = Path(exported["path"])
    assert path.suffix == f".{fmt}" and path.stat().st_size == exported["size"] > 0
    if fmt == "json":
        assert set(json.loads(path.read_text(encoding="utf-8"))) == {"case", "evidence", "facts", "wages"}
    elif fmt == "csv":
        assert path.read_text(encoding="utf-8-sig").splitlines()[0] == "period,expected_amount,paid_amount,arrears,payer,payer_relationship"
    elif fmt == "xlsx":
        with zipfile.ZipFile(path) as archive:
            assert "xl/workbook.xml" in archive.namelist()
    else:
        with zipfile.ZipFile(path) as archive:
            assert {"case.json", "wages.csv", "case.xlsx"}.issubset(archive.namelist())


@pytest.mark.parametrize("fmt", ["md", "json", "docx", "pdf"])
def test_v02_document_export_preserves_v01_formats(client, fmt):
    _, document = create_export_fixture(client)
    exported = envelope(client.post(f"/api/documents/{document['id']}/export", json={"format": fmt}))["data"]
    path = Path(exported["path"])
    assert path.suffix == f".{fmt}" and path.stat().st_size == exported["size"] > 0
    if fmt == "md":
        assert "不构成正式法律意见" in path.read_text(encoding="utf-8")
    elif fmt == "json":
        assert set(json.loads(path.read_text(encoding="utf-8"))) == {"document", "sources"}
    elif fmt == "docx":
        with zipfile.ZipFile(path) as archive:
            assert "word/document.xml" in archive.namelist()
    else:
        assert path.read_bytes().startswith(b"%PDF-")
