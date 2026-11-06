from __future__ import annotations

import io
import zipfile
from decimal import Decimal
from pathlib import Path

import pytest
from docx import Document as DocxDocument
from openpyxl import Workbook
from reportlab.pdfgen import canvas


def assert_envelope(response, status=200):
    assert response.status_code == status, response.text
    body = response.json()
    assert body.keys() == {"success", "data", "error", "meta"}
    assert body["success"] is True
    return body


def upload_and_process(client, case_id, text="2025年3月1日入职，约定工资6000元。\n2026年1月工资仅转账1000元，之后欠薪。"):
    up = assert_envelope(client.post(f"/api/cases/{case_id}/evidence", files={"file": ("notes.txt", text.encode(), "text/plain")}), 201)
    ev_id = up["data"]["id"]
    processed = assert_envelope(client.post(f"/api/evidence/{ev_id}/process"))
    return ev_id, processed


def test_case_crud_parties_and_owner_isolation(client, case_id):
    case = assert_envelope(client.get(f"/api/cases/{case_id}"))["data"]
    assert case["parties"][0]["name"] == "测试用户甲"
    assert_envelope(client.patch(f"/api/cases/{case_id}", json={"summary": "虚构测试数据"}))
    hidden = client.get(f"/api/cases/{case_id}", headers={"X-Owner-ID": "other-user"})
    assert hidden.status_code == 404 and hidden.json()["error"]["code"] == "CASE_NOT_FOUND"


def test_upload_hash_duplicate_and_security(client, case_id):
    first = assert_envelope(client.post(f"/api/cases/{case_id}/evidence", files={"file": ("a.txt", b"same", "text/plain")}), 201)
    second = assert_envelope(client.post(f"/api/cases/{case_id}/evidence", files={"file": ("a.txt", b"same", "text/plain")}), 201)
    assert first["data"]["sha256"] == second["data"]["sha256"] and second["meta"]["duplicate"] is True
    bad_type = client.post(f"/api/cases/{case_id}/evidence", files={"file": ("run.exe", b"x", "application/octet-stream")})
    assert bad_type.status_code == 400 and bad_type.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"
    traversal = client.post(f"/api/cases/{case_id}/evidence", files={"file": ("../evil.txt", b"x", "text/plain")})
    assert traversal.status_code == 400
    too_large = client.post(f"/api/cases/{case_id}/evidence", files={"file": ("large.txt", b"x" * 1025, "text/plain")})
    assert too_large.status_code == 413


def test_real_txt_processing_and_provenance(client, case_id):
    ev_id, result = upload_and_process(client, case_id)
    assert result["data"]["pages"][0]["ocr_engine"] == "text-parser"
    assert result["data"]["candidate_facts"]
    fact = result["data"]["candidate_facts"][0]
    assert fact["source_evidence_id"] == ev_id and fact["source_quote"]
    ocr = assert_envelope(client.get(f"/api/evidence/{ev_id}/ocr"))["data"]
    assert "约定工资" in ocr["pages"][0]["ocr_text"]


def parser_file(kind):
    if kind == "csv":
        return "ledger.csv", "period,amount\n2026-01,6000\n".encode(), "2026-01", "csv-parser"
    if kind == "docx":
        stream = io.BytesIO(); doc = DocxDocument(); doc.add_paragraph("2026 salary record"); doc.save(stream)
        return "record.docx", stream.getvalue(), "salary record", "python-docx"
    if kind == "pdf":
        stream = io.BytesIO(); pdf = canvas.Canvas(stream); pdf.drawString(40, 800, "2026 salary record"); pdf.save()
        return "record.pdf", stream.getvalue(), "salary record", "pypdf"
    stream = io.BytesIO(); wb = Workbook(); wb.active.append(["period", "amount"]); wb.active.append(["2026-01", 6000]); wb.save(stream)
    return "ledger.xlsx", stream.getvalue(), "2026-01", "openpyxl"


@pytest.mark.parametrize("kind", ["csv", "docx", "pdf", "xlsx"])
def test_real_structured_document_parsers(client, case_id, monkeypatch, kind):
    from app import services
    monkeypatch.setattr(services, "MAX_UPLOAD_BYTES", 2 * 1024 * 1024)
    filename, content, expected, engine = parser_file(kind)
    ev = assert_envelope(client.post(f"/api/cases/{case_id}/evidence", files={"file": (filename, content, "application/octet-stream")}), 201)["data"]
    processed = assert_envelope(client.post(f"/api/evidence/{ev['id']}/process"))["data"]
    assert processed["pages"][0]["ocr_engine"] == engine
    assert expected in processed["pages"][0]["ocr_text"]


def test_image_ocr_failure_is_explicit_degradation(client, case_id):
    ev = assert_envelope(client.post(f"/api/cases/{case_id}/evidence", files={"file": ("chat.png", b"not-a-real-image", "image/png")}), 201)["data"]
    processed = assert_envelope(client.post(f"/api/evidence/{ev['id']}/process"))["data"]
    assert processed["evidence"]["processing_status"] == "degraded"
    assert "manual transcription" in processed["warning"]
    assert processed["candidate_facts"] == []


def test_machine_extraction_marks_conflicting_candidates(client, case_id):
    _, result = upload_and_process(client, case_id, "2026年1月约定工资6000元\n2026年1月约定工资7000元")
    facts = result["data"]["candidate_facts"]
    assert len(facts) == 2
    assert {f["review_status"] for f in facts} == {"conflicted"}
    assert len({f["conflict_group_id"] for f in facts}) == 1


def test_fact_review_transitions_and_original_preserved(client, case_id):
    _, result = upload_and_process(client, case_id)
    facts = result["data"]["candidate_facts"]
    first, second = facts[0], facts[-1]
    patched = assert_envelope(client.patch(f"/api/facts/{first['id']}", json={"user_corrected_value": "2025年3月入职"}))["data"]
    assert patched["object_value"] == first["object_value"] and patched["user_corrected_value"] != patched["object_value"]
    confirmed = assert_envelope(client.post(f"/api/facts/{first['id']}/confirm"))["data"]
    assert confirmed["review_status"] == "user_confirmed" and confirmed["confirmed_at"]
    rejected = assert_envelope(client.post(f"/api/facts/{second['id']}/reject"))["data"]
    assert rejected["review_status"] == "user_rejected"
    assert client.post(f"/api/facts/{second['id']}/confirm").status_code == 409


def test_timeline_uses_only_confirmed_and_deduplicates(client, case_id):
    _, result = upload_and_process(client, case_id, "2025年3月1日入职\n2025年3月1日入职\n2026年1月欠薪")
    facts = result["data"]["candidate_facts"]
    for fact in facts[:2]: assert_envelope(client.post(f"/api/facts/{fact['id']}/confirm"))
    timeline = assert_envelope(client.post(f"/api/cases/{case_id}/timeline/rebuild"))["data"]
    assert len(timeline) == 1
    assert timeline[0]["source_fact_id"] in {facts[0]["id"], facts[1]["id"]}


def test_decimal_wages_partial_multi_payment_and_third_party(client, case_id):
    entry = assert_envelope(client.post(f"/api/cases/{case_id}/wages", json={"period": "2026-01", "expected_amount": "6000.10", "payments": [{"amount": "1000.05", "payer": "第三人乙", "payer_relationship": "payroll_intermediary"}, {"amount": "500.01", "payer": "公司"}]}), 201)["data"]
    assert entry["actual_paid_amount"] == "1500.06" and entry["arrears"] == "4500.04"
    summary = assert_envelope(client.post(f"/api/cases/{case_id}/calculations/recalculate"))["data"]
    assert summary["wages"] == {"expected": "6000.10", "paid": "1500.06", "arrears": "4500.04"}
    assert summary["economic_compensation"]["status"] == "missing_inputs"


def test_preliminary_economic_compensation_is_decimal_and_explains_limits(client, case_id):
    assert_envelope(client.patch(f"/api/cases/{case_id}", json={"employment_start_date": "2024-01-01", "employment_end_date": "2025-08-01"}))
    assert_envelope(client.post(f"/api/cases/{case_id}/wages", json={"period": "2025-07", "expected_amount": "6000.00"}), 201)
    result = assert_envelope(client.post(f"/api/cases/{case_id}/calculations/recalculate"))["data"]["economic_compensation"]
    assert result["service_months"] == 19 and result["compensation_months"] == "2"
    assert result["amount"] == "12000.00" and "人工复核" in result["warning"]


def test_claim_gap_and_adversarial_workflows_are_bounded(client, case_id):
    claim = assert_envelope(client.post(f"/api/cases/{case_id}/claims", json={"claim_type": "wage_arrears", "title": "支付拖欠工资", "amount": "4500.04"}), 201)["data"]
    assert Decimal(claim["amount"]) == Decimal("4500.04")
    gaps = assert_envelope(client.post(f"/api/cases/{case_id}/gap-analysis"))["data"]
    assert gaps["basis"] == "confirmed_facts_only" and gaps["llm_used"] is False
    review = assert_envelope(client.post(f"/api/cases/{case_id}/adversarial-review"))["data"]
    assert review["invented_opponent_evidence"] is False and all(x["certainty"] == "possibility_only" for x in review["arguments"])


def test_documents_confirmed_only_versions_and_all_exports(client, case_id):
    _, result = upload_and_process(client, case_id, "2025年3月1日入职\n2026年1月欠薪")
    facts = result["data"]["candidate_facts"]
    assert_envelope(client.post(f"/api/facts/{facts[0]['id']}/confirm"))
    first = assert_envelope(client.post(f"/api/cases/{case_id}/documents/generate", json={"document_type": "arbitration_application"}), 201)["data"]
    second = assert_envelope(client.post(f"/api/cases/{case_id}/documents/generate", json={"document_type": "arbitration_application"}), 201)["data"]
    assert second["version"] == first["version"] + 1
    assert facts[0]["object_value"] in second["content_markdown"]
    assert facts[-1]["object_value"] not in second["content_markdown"]
    for fmt in ["md", "json", "docx", "pdf"]:
        exported = assert_envelope(client.post(f"/api/documents/{second['id']}/export", json={"format": fmt}))["data"]
        assert Path(exported["path"]).exists() and exported["size"] > 0
    for fmt in ["json", "csv", "xlsx", "zip"]:
        exported = assert_envelope(client.post(f"/api/cases/{case_id}/export", json={"format": fmt}))["data"]
        assert Path(exported["path"]).exists() and exported["size"] > 0
    zip_path = Path(assert_envelope(client.post(f"/api/cases/{case_id}/export", json={"format": "zip"}))["data"]["path"])
    with zipfile.ZipFile(zip_path) as zf:
        assert {
            "README-案件说明.md",
            "01-案件事实摘要.docx",
            "02-劳动仲裁申请书草稿.docx",
            "03-证据目录.xlsx",
            "04-欠薪明细.xlsx",
            "05-案件时间线.xlsx",
            "06-待补证清单.docx",
            "extracted/confirmed-facts.json",
            "extracted/timeline.json",
            "audit/export-manifest.json",
        }.issubset(zf.namelist())


def test_delete_case_cascades_database_and_private_files(client, case_id):
    ev_id, _ = upload_and_process(client, case_id)
    evidence = assert_envelope(client.get(f"/api/evidence/{ev_id}"))["data"]
    original = Path(__import__("os").environ["STORAGE_ROOT"]) / case_id / "original" / evidence["stored_filename"]
    assert original.exists()
    assert_envelope(client.delete(f"/api/cases/{case_id}"))
    assert client.get(f"/api/evidence/{ev_id}").status_code == 404
    assert not original.parent.parent.exists()


def test_system_health_providers_and_self_check(client):
    assert assert_envelope(client.get("/api/system/health"))["data"]["status"] == "healthy"
    providers = assert_envelope(client.get("/api/system/providers"))["data"]
    assert providers["llm"] == {"provider": "disabled", "enabled": False, "fabricates_fallback": False}
    check = assert_envelope(client.get("/api/system/self-check"))["data"]
    assert check["status"] == "passed"
    assert not [x for x in check["checks"] if x["status"] == "failed"]


def test_local_frontend_origin_receives_cors_headers(client):
    response = client.options(
        "/api/cases",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
