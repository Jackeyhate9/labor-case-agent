from __future__ import annotations

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image

from app.providers.ocr import (
    OCRPageResult,
    OCRResult,
    OCRRouter,
    OllamaOCRProvider,
    UnlimitedOCRProvider,
)


def envelope(response, status=200):
    assert response.status_code == status, response.text
    body = response.json()
    assert body["success"] is True
    return body["data"]


def test_ollama_ocr_posts_vision_image_to_generate_endpoint(monkeypatch, tmp_path):
    requests = []

    class GenerateHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers["Content-Length"])
            requests.append(
                {
                    "path": self.path,
                    "body": json.loads(self.rfile.read(length)),
                }
            )
            payload = json.dumps({"response": "工资尚欠 12000 元"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), GenerateHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        image_path = tmp_path / "evidence.png"
        Image.new("RGB", (20, 10), "white").save(image_path)
        monkeypatch.setenv("OLLAMA_BASE_URL", f"http://127.0.0.1:{server.server_port}")
        monkeypatch.setenv("OLLAMA_OCR_MODEL", "unlimitedocrlocal:latest")

        result = OllamaOCRProvider().recognize_image(image_path)

        assert result.provider == "ollama-ocr"
        assert result.device == "ollama"
        assert result.pages[0].text == "工资尚欠 12000 元"
        assert (result.pages[0].width, result.pages[0].height) == (20, 10)
        assert requests[0]["path"] == "/api/generate"
        assert requests[0]["body"]["model"] == "unlimitedocrlocal:latest"
        assert requests[0]["body"]["stream"] is False
        assert base64.b64decode(requests[0]["body"]["images"][0]) == image_path.read_bytes()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_ollama_ocr_failure_falls_back_to_rapidocr(monkeypatch, tmp_path):
    class FailingHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(500)
            self.end_headers()

        def log_message(self, _format, *_args):
            return

    class RapidFallback:
        name = "rapidocr"

        def availability(self):
            return True, "available"

        def recognize_image(self, _path):
            return OCRResult(
                pages=[OCRPageResult("本地降级识别")],
                provider=self.name,
                device="cpu",
            )

    server = ThreadingHTTPServer(("127.0.0.1", 0), FailingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        image_path = tmp_path / "evidence.png"
        Image.new("RGB", (20, 10), "white").save(image_path)
        monkeypatch.setenv("OLLAMA_BASE_URL", f"http://127.0.0.1:{server.server_port}")
        monkeypatch.setenv("OLLAMA_OCR_MODEL", "unlimitedocrlocal:latest")

        result = OCRRouter([OllamaOCRProvider(), RapidFallback()]).recognize_image(image_path)

        assert result.provider == "rapidocr"
        assert result.pages[0].text == "本地降级识别"
        assert result.fallback_reasons == ["ollama-ocr:failed:HTTPStatusError"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_ollama_ocr_can_be_selected_and_reports_configuration(client, monkeypatch, tmp_path):
    monkeypatch.setenv("SYSTEM_SETTINGS_FILE", str(tmp_path / "system-settings.json"))
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("OLLAMA_OCR_MODEL", "unlimitedocrlocal:latest")

    data = envelope(
        client.patch(
            "/api/system/settings",
            json={"ocr_provider": "ollama-ocr"},
        )
    )

    assert data["ocr_provider"] == "ollama-ocr"
    assert data["providers"]["ocr"]["selected"] == "ollama-ocr"
    assert data["providers"]["ocr"]["effective"] == "ollama-ocr"
    assert data["providers"]["ocr"]["candidates"]["ollama-ocr"] is True


def test_unlimited_ocr_accepts_an_external_runtime_without_api_process_dependencies(
    monkeypatch, tmp_path
):
    model = tmp_path / "Unlimited-OCR"
    model.mkdir()
    runtime = tmp_path / "python.exe"
    runtime.write_bytes(b"external python")
    monkeypatch.setenv("UNLIMITED_OCR_MODEL_PATH", str(model))
    monkeypatch.setenv("UNLIMITED_OCR_PYTHON", str(runtime))
    monkeypatch.setattr(
        "app.providers.ocr.importlib.util.find_spec",
        lambda _name: None,
    )

    assert UnlimitedOCRProvider().availability() == (True, "available_external_runtime")
