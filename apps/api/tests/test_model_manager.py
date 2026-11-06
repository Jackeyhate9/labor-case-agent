def test_model_manager_describes_ready_basic_mode_and_optional_packs(client, monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_ROOT", str(tmp_path / "models"))
    monkeypatch.setenv("MODEL_RUNTIME_ROOT", str(tmp_path / "runtimes"))
    monkeypatch.setenv("MODEL_MANAGER_STATE_FILE", str(tmp_path / "model-manager.json"))

    response = client.get("/api/system/model-manager")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["basic_mode"]["ready"] is True
    assert data["basic_mode"]["provider"] == "rapidocr"
    assert data["onboarding_required"] is True
    assert data["automatic_downloads"] is False
    assert {pack["id"] for pack in data["packs"]} == {
        "unlimited-ocr",
        "moss-transcribe-diarize",
        "bge-m3",
        "nemotron-embed",
    }
    assert all(pack["requires_consent"] for pack in data["packs"])
    assert all(pack["revision"] for pack in data["packs"])
    assert all(pack["model_bytes"] > 0 and pack["runtime_bytes"] > 0 for pack in data["packs"])


def test_model_install_requires_explicit_license_and_download_consent(client, monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_ROOT", str(tmp_path / "models"))
    monkeypatch.setenv("MODEL_RUNTIME_ROOT", str(tmp_path / "runtimes"))
    monkeypatch.setenv("MODEL_MANAGER_STATE_FILE", str(tmp_path / "model-manager.json"))

    response = client.post(
        "/api/system/models/bge-m3/install",
        json={"accept_license": False, "accept_download": True},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "MODEL_CONSENT_REQUIRED"


def test_model_install_downloads_and_verifies_catalog_artifact(client, monkeypatch, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    payload = b"verified model payload"
    (source / "model.safetensors").write_bytes(payload)

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        partial(QuietHandler, directory=str(source)),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        pack = model_manager.ModelPack(
            id="test-pack",
            name="测试能力包",
            capability="test",
            description="public API download test",
            repo_id="local/test",
            revision="test-revision",
            folder="test-pack",
            license="MIT",
            model_bytes=len(payload),
            runtime_bytes=0,
            runtime="none",
            python_version="none",
            hardware="cpu",
            minimum_vram_gb=0,
            artifacts=(
                model_manager.DownloadArtifact(
                    url=f"http://127.0.0.1:{server.server_port}/model.safetensors",
                    path="model.safetensors",
                    sha256=hashlib.sha256(payload).hexdigest(),
                    size=len(payload),
                ),
            ),
        )
        monkeypatch.setattr(model_manager, "PACKS", (pack,))
        monkeypatch.setenv("MODEL_ROOT", str(tmp_path / "models"))
        monkeypatch.setenv("MODEL_RUNTIME_ROOT", str(tmp_path / "runtimes"))
        monkeypatch.setenv("MODEL_MANAGER_STATE_FILE", str(tmp_path / "model-manager.json"))

        start = client.post(
            "/api/system/models/test-pack/install",
            json={"accept_license": True, "accept_download": True},
        )
        assert start.status_code == 202
        job_id = start.json()["data"]["id"]

        job = None
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            response = client.get(f"/api/system/model-jobs/{job_id}")
            assert response.status_code == 200
            job = response.json()["data"]
            if job["status"] in {"completed", "failed"}:
                break
            time.sleep(0.02)

        assert job and job["status"] == "completed", job
        assert job["downloaded_bytes"] == len(payload)
        assert (tmp_path / "models" / "test-pack" / "model.safetensors").read_bytes() == payload
    finally:
        server.shutdown()
        server.server_close()


def test_user_can_keep_basic_mode_without_being_prompted_again(client, monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_ROOT", str(tmp_path / "models"))
    monkeypatch.setenv("MODEL_RUNTIME_ROOT", str(tmp_path / "runtimes"))
    monkeypatch.setenv("MODEL_MANAGER_STATE_FILE", str(tmp_path / "model-manager.json"))

    response = client.post(
        "/api/system/model-manager/onboarding",
        json={"choice": "basic"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["onboarding_required"] is False
    assert client.get("/api/system/model-manager").json()["data"]["onboarding_required"] is False
import hashlib
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from app import model_manager
