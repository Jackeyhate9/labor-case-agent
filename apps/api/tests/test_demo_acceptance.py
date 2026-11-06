from __future__ import annotations

import json
import zipfile
from pathlib import Path

from app import services


DEMO = Path(__file__).resolve().parents[3] / "samples" / "demo-case"


def data(response, status=200):
    assert response.status_code == status, response.text
    payload = response.json()
    assert payload["success"] is True
    return payload["data"]


def test_empty_database_to_real_demo_archive_acceptance(client, monkeypatch):
    monkeypatch.setattr(services, "MAX_UPLOAD_BYTES", 5 * 1024 * 1024)
    case = data(
        client.post(
            "/api/cases",
            json={
                "title": "测试用户甲欠薪案（完全虚构）",
                "case_type": "wage_arrears,employment_relation,termination",
                "jurisdiction_region": "北京市（测试）",
                "employment_start_date": "2024-07-01",
                "employment_end_date": "2026-06-30",
                "parties": [
                    {"party_type": "worker", "name": "测试用户甲"},
                    {"party_type": "company", "name": "北京某某文化传媒有限公司（虚构）"},
                    {"party_type": "payroll_intermediary", "name": "测试第三人乙"},
                ],
            },
        ),
        201,
    )
    case_id = case["id"]

    evidence_ids = []
    for filename in [
        "chat-01.png",
        "chat-02.png",
        "bank-transactions.csv",
        "social-insurance.pdf",
        "work-record.docx",
        "rental-note.txt",
    ]:
        path = DEMO / filename
        uploaded = data(
            client.post(
                f"/api/cases/{case_id}/evidence",
                files={"file": (filename, path.read_bytes(), "application/octet-stream")},
            ),
            201,
        )
        evidence_ids.append(uploaded["id"])
        processed = data(client.post(f"/api/evidence/{uploaded['id']}/process"))
        if filename.endswith(".png"):
            assert processed["pages"][0]["ocr_engine"] == "rapidocr"
            assert processed["warning"] is None

    facts = data(client.get(f"/api/cases/{case_id}/facts"))
    assert len(facts) >= 6
    confirmed_ids = []
    for fact in facts[:4]:
        confirmed = data(client.post(f"/api/facts/{fact['id']}/confirm"))
        confirmed_ids.append(confirmed["id"])
    data(client.post(f"/api/facts/{facts[-1]['id']}/reject"))
    unconfirmed_value = next(
        f["object_value"] for f in facts if f["id"] not in confirmed_ids and f["id"] != facts[-1]["id"]
    )

    timeline = data(client.post(f"/api/cases/{case_id}/timeline/rebuild"))
    assert timeline
    assert all(event["source_fact_id"] in confirmed_ids for event in timeline)

    data(
        client.post(
            f"/api/cases/{case_id}/wages",
            json={
                "period": "2026-02",
                "expected_amount": "6000.00",
                "payments": [
                    {
                        "amount": "1000.00",
                        "payer": "测试第三人乙",
                        "payer_relationship": "payroll_intermediary",
                        "payment_date": "2026-02-20",
                    }
                ],
                "notes": "部分支付；款项性质已由测试用户确认",
            },
        ),
        201,
    )
    calculation = data(client.post(f"/api/cases/{case_id}/calculations/recalculate"))
    assert calculation["wages"]["arrears"] == "5000.00"

    for claim_type, title, amount in [
        ("employment_relation", "确认劳动关系", None),
        ("wage_arrears", "支付拖欠工资", "5000.00"),
        ("economic_compensation", "支付经济补偿（待复核）", None),
    ]:
        data(
            client.post(
                f"/api/cases/{case_id}/claims",
                json={"claim_type": claim_type, "title": title, "amount": amount},
            ),
            201,
        )
    assert data(client.post(f"/api/cases/{case_id}/gap-analysis"))["basis"] == "confirmed_facts_only"
    assert data(client.post(f"/api/cases/{case_id}/adversarial-review"))["invented_opponent_evidence"] is False

    first = data(
        client.post(
            f"/api/cases/{case_id}/documents/generate",
            json={"document_type": "arbitration_application"},
        ),
        201,
    )
    second = data(
        client.post(
            f"/api/cases/{case_id}/documents/generate",
            json={"document_type": "arbitration_application"},
        ),
        201,
    )
    assert second["version"] == first["version"] + 1
    assert unconfirmed_value not in second["content_markdown"]

    archive_path = Path(data(client.post(f"/api/cases/{case_id}/export", json={"format": "zip"}))["path"])
    assert archive_path.exists()
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        required = set(json.loads((DEMO / "expected-results.json").read_text(encoding="utf-8"))["required_export_members"])
        assert required.issubset(names)
        assert any(name.startswith("extracted/ocr/EV-001") for name in names)
        assert len([name for name in names if name.startswith("evidence/EV-")]) == len(evidence_ids)
        assert all(
            archive.getinfo(name).compress_type == zipfile.ZIP_STORED
            for name in names
            if name.startswith("evidence/EV-")
        )
        confirmed = json.loads(archive.read("extracted/confirmed-facts.json"))
        assert confirmed and all(fact["review_status"] == "user_confirmed" for fact in confirmed)
        manifest = json.loads(archive.read("audit/export-manifest.json"))
        assert manifest["confirmed_fact_count"] == len(confirmed_ids)
        assert manifest["calculation"]["arrears"] == "5000.00"

    self_check = data(client.get("/api/system/self-check"))
    assert self_check["status"] == "passed"
    assert not any(item["status"] == "failed" for item in self_check["checks"])
