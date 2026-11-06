from __future__ import annotations

import json
import os

import pytest


@pytest.fixture(autouse=True)
def restore_profile_activated_environment():
    names = (
        "LLM_BASE_URL",
        "LLM_MODEL",
        "LLM_PROVIDER",
        "OLLAMA_OCR_MODEL",
        "OCR_PROVIDER",
        "AUDIO_PROVIDER",
        "EMBEDDING_PROVIDER",
    )
    snapshot = {name: os.environ.get(name) for name in names}
    yield
    for name, value in snapshot.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def envelope(response, status=200):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"success", "data", "error", "meta"}
    assert body["success"] is True
    return body["data"]


def test_distribution_is_the_safe_user_managed_default(client, monkeypatch, tmp_path):
    monkeypatch.delenv("APP_EDITION", raising=False)
    monkeypatch.delenv("MODEL_ROOT", raising=False)
    monkeypatch.setenv("MODEL_ROOT_REGISTRY_FILE", str(tmp_path / "model-root.json"))

    data = envelope(client.get("/api/system/app-profile"))

    assert data["edition"] == "distribution"
    assert data["configuration_mode"] == "user"
    assert data["locked"] is False
    assert data["model_root"]["source"] == "default"
    assert data["model_root"]["registration_allowed"] is True


def test_roadshow_profile_activates_existing_environment_managed_capabilities(
    client, monkeypatch, tmp_path
):
    runtime = tmp_path / "python.exe"
    runtime.write_bytes(b"external runtime")
    unlimited = tmp_path / "Unlimited-OCR"
    moss = tmp_path / "MOSS-Transcribe-Diarize"
    bge = tmp_path / "bge-m3"
    nemotron = tmp_path / "Nemotron-3-Embed-1B-BF16"
    for directory in (unlimited, moss, bge, nemotron):
        directory.mkdir()
        (directory / "model.safetensors").write_bytes(b"existing model")
    monkeypatch.setenv("APP_EDITION", "roadshow")
    monkeypatch.setenv("SYSTEM_SETTINGS_FILE", str(tmp_path / "system-settings.json"))
    monkeypatch.setenv("MODEL_ROOT", str(tmp_path))
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:8b")
    monkeypatch.setenv("UNLIMITED_OCR_MODEL_PATH", str(unlimited))
    monkeypatch.setenv("UNLIMITED_OCR_PYTHON", str(runtime))
    monkeypatch.setenv("MOSS_MODEL_PATH", str(moss))
    monkeypatch.setenv("MOSS_PYTHON", str(runtime))
    monkeypatch.setenv("BGE_M3_MODEL_PATH", str(bge))
    monkeypatch.setenv("NEMOTRON_EMBED_MODEL_PATH", str(nemotron))
    monkeypatch.setenv("EMBEDDING_PYTHON", str(runtime))

    data = envelope(client.get("/api/system/app-profile"))

    assert data["edition"] == "roadshow"
    assert data["configuration_mode"] == "environment"
    assert data["locked"] is True
    assert data["providers"] == {
        "llm": "ollama",
        "ocr": "unlimited-ocr",
        "audio": "moss-transcribe-diarize",
        "embedding": "bge-m3",
    }
    assert all(
        data["assets"][name]["configured"]
        for name in ("ollama", "unlimited_ocr", "moss", "bge_m3", "nemotron")
    )
    assert data["model_root"]["source"] == "environment"
    assert os.environ["LLM_BASE_URL"] == "http://127.0.0.1:11434"
    assert os.environ["LLM_MODEL"] == "qwen3:8b"
    assert os.environ["LLM_PROVIDER"] == "ollama"
    assert os.environ["OCR_PROVIDER"] == "unlimited-ocr"
    assert os.environ["AUDIO_PROVIDER"] == "moss-transcribe-diarize"
    assert os.environ["EMBEDDING_PROVIDER"] == "bge-m3"
    manager = envelope(client.get("/api/system/model-manager"))
    assert all(pack["installed"] for pack in manager["packs"])
    settings = envelope(client.get("/api/system/settings"))
    assert settings["llm_provider"] == "ollama"
    assert settings["ocr_provider"] == "unlimited-ocr"
    assert settings["audio_provider"] == "moss-transcribe-diarize"
    assert settings["embedding_provider"] == "bge-m3"
    assert settings["providers"]["llm"]["selected"] == "ollama"
    assert settings["providers"]["ocr"]["selected"] == "unlimited-ocr"
    assert settings["profile"] == {
        "edition": "roadshow",
        "locked": True,
        "source": "environment",
    }
    assert envelope(client.get("/api/system/llm-config"))["provider"] == "ollama"

    rejected = client.patch(
        "/api/system/settings",
        json={"ocr_provider": "rapidocr"},
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "APP_PROFILE_LOCKED"


def test_existing_model_root_is_registered_in_place_without_copying(
    client, monkeypatch, tmp_path
):
    root = tmp_path / "existing-models"
    model = root / "bge-m3"
    model.mkdir(parents=True)
    weights = model / "model.safetensors"
    weights.write_bytes(b"existing weights stay here")
    registry = tmp_path / "model-root.json"
    monkeypatch.delenv("MODEL_ROOT", raising=False)
    monkeypatch.setenv("MODEL_ROOT_REGISTRY_FILE", str(registry))
    monkeypatch.setenv("MODEL_RUNTIME_ROOT", str(tmp_path / "runtimes"))
    monkeypatch.setenv("MODEL_MANAGER_STATE_FILE", str(tmp_path / "manager-state.json"))

    data = envelope(
        client.post(
            "/api/system/model-manager/register-root",
            json={"path": str(root)},
        )
    )

    assert data["registered"] is True
    assert data["copied"] is False
    assert data["recognized_packs"] == ["bge-m3"]
    assert data["model_root"]["path"] == str(root.resolve())
    assert json.loads(registry.read_text(encoding="utf-8"))["path"] == str(root.resolve())
    assert weights.read_bytes() == b"existing weights stay here"
    manager = envelope(client.get("/api/system/model-manager"))
    assert manager["model_root"] == str(root.resolve())
    bge = next(pack for pack in manager["packs"] if pack["id"] == "bge-m3")
    assert bge["model_present"] is True
    assert bge["runtime_present"] is False


def test_launcher_data_root_contract_is_visible_to_the_frontend(
    client, monkeypatch, tmp_path
):
    home = tmp_path / "roadshow-home"
    data_root = tmp_path / "roadshow-data"
    monkeypatch.setenv("LABOR_CASE_AGENT_HOME", str(home))
    monkeypatch.setenv("APP_DATA_ROOT", str(data_root))

    data = envelope(client.get("/api/system/app-profile"))

    assert data["storage"] == {
        "home": str(home.resolve()),
        "data_root": str(data_root.resolve()),
        "source": "app_data_root",
    }


def test_roadshow_defaults_to_ollama_vision_ocr_when_external_unlimited_is_absent(
    client, monkeypatch, tmp_path
):
    monkeypatch.setenv("APP_EDITION", "roadshow")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:8b")
    monkeypatch.delenv("OLLAMA_OCR_MODEL", raising=False)
    monkeypatch.delenv("UNLIMITED_OCR_MODEL_PATH", raising=False)
    monkeypatch.delenv("UNLIMITED_OCR_PYTHON", raising=False)

    data = envelope(client.get("/api/system/app-profile"))

    assert os.environ["OLLAMA_OCR_MODEL"] == "unlimitedocrlocal:latest"
    assert os.environ["OCR_PROVIDER"] == "ollama-ocr"
    assert data["providers"]["ocr"] == "ollama-ocr"
    assert data["assets"]["ollama_ocr"] == {
        "configured": True,
        "base_url": "http://127.0.0.1:11434",
        "model": "unlimitedocrlocal:latest",
    }


def test_registered_root_cannot_override_launcher_managed_model_root(
    client, monkeypatch, tmp_path
):
    launcher_root = tmp_path / "launcher-models"
    candidate = tmp_path / "candidate-models"
    launcher_root.mkdir()
    candidate.mkdir()
    registry = tmp_path / "model-root.json"
    monkeypatch.setenv("APP_EDITION", "roadshow")
    monkeypatch.setenv("MODEL_ROOT", str(launcher_root))
    monkeypatch.setenv("MODEL_ROOT_REGISTRY_FILE", str(registry))

    response = client.post(
        "/api/system/model-manager/register-root",
        json={"path": str(candidate)},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "MODEL_ROOT_MANAGED_BY_ENVIRONMENT"
    assert not registry.exists()


def test_registered_root_rejects_directories_without_known_model_weights(
    client, monkeypatch, tmp_path
):
    candidate = tmp_path / "empty-models"
    candidate.mkdir()
    monkeypatch.delenv("MODEL_ROOT", raising=False)
    monkeypatch.setenv("MODEL_ROOT_REGISTRY_FILE", str(tmp_path / "model-root.json"))

    response = client.post(
        "/api/system/model-manager/register-root",
        json={"path": str(candidate)},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "MODEL_ROOT_EMPTY"


def test_distribution_registry_can_override_the_launcher_default_model_directory(
    client, monkeypatch, tmp_path
):
    launcher_default = tmp_path / "launcher-default"
    launcher_default.mkdir()
    candidate = tmp_path / "existing-models"
    model = candidate / "bge-m3"
    model.mkdir(parents=True)
    (model / "model.safetensors").write_bytes(b"existing model")
    monkeypatch.setenv("APP_EDITION", "distribution")
    monkeypatch.setenv("APP_CONFIGURATION_MODE", "user")
    monkeypatch.setenv("MODEL_ROOT", str(launcher_default))
    monkeypatch.setenv("MODEL_ROOT_REGISTRY_FILE", str(tmp_path / "model-root.json"))

    data = envelope(
        client.post(
            "/api/system/model-manager/register-root",
            json={"path": str(candidate)},
        )
    )

    assert data["model_root"]["path"] == str(candidate.resolve())
    assert data["model_root"]["source"] == "registered"
