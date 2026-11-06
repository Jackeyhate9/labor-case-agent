from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from app.providers.audio import MOSSAudioProvider
from app.providers.embedding import embedding_configuration
from app.providers.ocr import PaddleOCRProvider, RapidOCRProvider, UnlimitedOCRProvider, WindowsOCRProvider


def data(response, status=200):
    assert response.status_code == status, response.text
    body = response.json()
    assert body["success"] is True
    return body["data"]


def test_v01_collection_and_detail_endpoints_remain_operational(client, case_id):
    assert any(item["id"] == case_id for item in data(client.get("/api/cases")))
    evidence = data(client.post(f"/api/cases/{case_id}/evidence", files={"file": ("note.txt", "2026年1月欠薪6000元".encode(), "text/plain")}), 201)
    assert data(client.get(f"/api/cases/{case_id}/evidence"))[0]["id"] == evidence["id"]
    processed = data(client.post(f"/api/evidence/{evidence['id']}/process"))
    assert data(client.get(f"/api/evidence/{evidence['id']}/extractions"))[0]["id"] == processed["candidate_facts"][0]["id"]


def test_v01_wage_claim_and_document_update_read_endpoints(client, case_id):
    wage = data(client.post(f"/api/cases/{case_id}/wages", json={"period": "2026-01", "expected_amount": "6000"}), 201)
    updated_wage = data(client.patch(f"/api/wages/{wage['id']}", json={"period": "2026-01", "expected_amount": "6000", "paid_amount": "1000"}))
    assert Decimal(updated_wage["arrears"]) == Decimal("5000.00")
    assert data(client.get(f"/api/cases/{case_id}/wages"))["summary"]["arrears"] == "5000.00"
    claim = data(client.post(f"/api/cases/{case_id}/claims", json={"claim_type": "wage_arrears", "title": "支付工资"}), 201)
    updated_claim = data(client.patch(f"/api/claims/{claim['id']}", json={"claim_type": "wage_arrears", "title": "支付拖欠工资", "status": "reviewed"}))
    assert updated_claim["status"] == "reviewed"
    assert data(client.get(f"/api/cases/{case_id}/claims"))[0]["id"] == claim["id"]
    document = data(client.post(f"/api/cases/{case_id}/documents/generate", json={"document_type": "case_summary"}), 201)
    assert data(client.get(f"/api/cases/{case_id}/documents"))[0]["id"] == document["id"]
    assert data(client.get(f"/api/documents/{document['id']}"))["id"] == document["id"]


def test_rejected_fact_can_be_corrected_then_confirmed(client, case_id):
    evidence = data(client.post(f"/api/cases/{case_id}/evidence", files={"file": ("note.txt", "2026年1月欠薪6000元".encode(), "text/plain")}), 201)
    fact = data(client.post(f"/api/evidence/{evidence['id']}/process"))["candidate_facts"][0]
    data(client.post(f"/api/facts/{fact['id']}/reject"))
    corrected = data(client.patch(f"/api/facts/{fact['id']}", json={"user_corrected_value": "2026年1月欠薪5000元"}))
    assert corrected["review_status"] == "machine_extracted"
    assert data(client.post(f"/api/facts/{fact['id']}/confirm"))["review_status"] == "user_confirmed"
    data(client.post(f"/api/cases/{case_id}/timeline/rebuild"))
    assert data(client.get(f"/api/cases/{case_id}/timeline"))[0]["source_fact_id"] == fact["id"]


def test_export_download_enforces_safe_case_scoped_filename(client, case_id):
    exported = data(client.post(f"/api/cases/{case_id}/export", json={"format": "json"}))
    filename = Path(exported["path"]).name
    download = client.get(f"/api/cases/{case_id}/exports/{filename}")
    assert download.status_code == 200 and json.loads(download.content)["case"]["id"] == case_id
    assert client.get(f"/api/cases/{case_id}/exports/..%2Fevil.json").status_code in {400, 404}
    missing = client.get(f"/api/cases/{case_id}/exports/missing.json")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "EXPORT_NOT_FOUND"


def test_delete_evidence_removes_record_and_file(client, case_id):
    evidence = data(client.post(f"/api/cases/{case_id}/evidence", files={"file": ("delete.txt", b"delete me", "text/plain")}), 201)
    assert data(client.delete(f"/api/evidence/{evidence['id']}"))["deleted"] is True
    assert client.get(f"/api/evidence/{evidence['id']}").status_code == 404


@pytest.mark.parametrize(
    ("method", "url", "payload"),
    [
        ("patch", "/api/facts/00000000-0000-0000-0000-000000000000", {}),
        ("patch", "/api/wages/00000000-0000-0000-0000-000000000000", {"period": "2026-01", "expected_amount": "1"}),
        ("patch", "/api/claims/00000000-0000-0000-0000-000000000000", {"claim_type": "other", "title": "x"}),
        ("get", "/api/regions/00000000-0000-0000-0000-000000000000/crop", None),
    ],
)
def test_owned_resource_endpoints_return_structured_not_found(client, method, url, payload):
    response = getattr(client, method)(url, json=payload) if payload is not None else getattr(client, method)(url)
    assert response.status_code == 404 and response.json()["success"] is False


def test_audio_provider_availability_reports_real_missing_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("MOSS_PYTHON", str(tmp_path / "missing-python"))
    monkeypatch.setenv("MOSS_MODEL_PATH", str(tmp_path / "missing-model"))
    assert MOSSAudioProvider().availability() == (False, "runtime_not_installed")
    runtime = tmp_path / "python.exe"; runtime.write_text("", encoding="utf-8")
    monkeypatch.setenv("MOSS_PYTHON", str(runtime))
    assert MOSSAudioProvider().availability() == (False, "model_not_installed")
    model = tmp_path / "model"; model.mkdir(); monkeypatch.setenv("MOSS_MODEL_PATH", str(model))
    assert MOSSAudioProvider().availability() == (True, "available")


@pytest.mark.parametrize("provider", ["disabled", "unknown", "bge-m3", "nemotron-3-embed-1b"])
def test_embedding_configuration_reports_real_filesystem_state(monkeypatch, tmp_path, provider):
    monkeypatch.setenv("EMBEDDING_PROVIDER", provider)
    monkeypatch.setenv("EMBEDDING_PYTHON", sys.executable)
    monkeypatch.setenv("BGE_M3_MODEL_PATH", str(tmp_path / "missing-bge"))
    monkeypatch.setenv("NEMOTRON_EMBED_MODEL_PATH", str(tmp_path / "missing-nemotron"))
    config, reason = embedding_configuration()
    assert config is None
    assert reason in {"disabled", "unknown_provider", "model_not_installed"}


def test_embedding_configuration_accepts_complete_local_model_directory(monkeypatch, tmp_path):
    model = tmp_path / "bge"; model.mkdir(); (model / "model.safetensors").write_bytes(b"local-test-weight-marker")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "bge-m3")
    monkeypatch.setenv("EMBEDDING_PYTHON", sys.executable)
    monkeypatch.setenv("BGE_M3_MODEL_PATH", str(model))
    config, reason = embedding_configuration()
    assert reason == "available" and config is not None
    assert config.provider == "bge-m3" and config.model_path == model


def test_ocr_provider_availability_checks_are_lazy_and_do_not_load_models(monkeypatch, tmp_path):
    monkeypatch.setenv("UNLIMITED_OCR_MODEL_PATH", str(tmp_path / "missing"))
    states = {
        "rapid": RapidOCRProvider().availability(),
        "paddle": PaddleOCRProvider().availability(),
        "windows": WindowsOCRProvider().availability(),
        "unlimited": UnlimitedOCRProvider().availability(),
    }
    assert all(isinstance(value[0], bool) and isinstance(value[1], str) for value in states.values())
    assert states["unlimited"] == (False, "model_not_installed")
