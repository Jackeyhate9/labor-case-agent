def envelope(response, status=200):
    assert response.status_code == status, response.text
    payload = response.json()
    assert payload["success"] is True
    return payload["data"]


def add_facts(client, case_id):
    evidence = envelope(
        client.post(
            f"/api/cases/{case_id}/evidence",
            files={
                "file": (
                    "messages.txt",
                    "2024年7月入职，公司安排工作\n2026年2月欠薪6000元\n2026年3月未经确认的社保房租关系".encode(),
                    "text/plain",
                )
            },
        ),
        201,
    )
    processed = envelope(client.post(f"/api/evidence/{evidence['id']}/process"))
    for fact in processed["candidate_facts"][:2]:
        envelope(client.post(f"/api/facts/{fact['id']}/confirm"))
    return processed["candidate_facts"]


def test_evidence_review_agent_uses_only_confirmed_facts(client, case_id):
    facts = add_facts(client, case_id)
    review = envelope(client.post(f"/api/cases/{case_id}/evidence-review"))
    assert set(review) >= {"strengths", "weaknesses", "conflicts", "missing_materials"}
    referenced = {
        fact_id
        for section in ("strengths", "weaknesses", "conflicts")
        for item in review[section]
        for fact_id in item.get("fact_ids", [])
    }
    assert {facts[0]["id"], facts[1]["id"]} <= referenced
    assert facts[-1]["id"] not in referenced
    assert review["confirmed_facts_only"] is True
    assert review["invented_facts"] is False


def test_adversarial_review_includes_all_required_defense_scenarios(client, case_id):
    add_facts(client, case_id)
    review = envelope(client.post(f"/api/cases/{case_id}/adversarial-review"))
    scenarios = {item["scenario"] for item in review["arguments"]}
    assert scenarios == {
        "third_party_payment",
        "project_cooperation",
        "rent_payment_relationship",
        "no_fixed_payday",
        "no_written_contract",
        "late_social_insurance",
    }
    assert review["invented_opponent_evidence"] is False
    assert all(item["certainty"] == "possibility_only" for item in review["arguments"])


def test_upload_rejects_dangerous_double_extensions(client, case_id):
    response = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("工资表.xlsx.cmd", b"malware", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DANGEROUS_FILE_EXTENSION"


def test_upload_rejects_content_that_does_not_match_safe_extension(client, case_id):
    response = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("伪装材料.pdf", b"MZ\x90\x00not a pdf", "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "FILE_CONTENT_MISMATCH"


def test_text_preview_automatically_masks_identity_and_phone(client, case_id):
    text = "申请人身份证110105199001011234，手机号13800138000"
    evidence = envelope(
        client.post(
            f"/api/cases/{case_id}/evidence",
            files={"file": ("identity.txt", text.encode(), "text/plain")},
        ),
        201,
    )
    preview = envelope(client.get(f"/api/evidence/{evidence['id']}/preview/data"))
    assert "110105199001011234" not in preview["text"]
    assert "13800138000" not in preview["text"]
    assert "110105********1234" in preview["text"]
    assert "138****8000" in preview["text"]
    assert preview["contains_sensitive_data"] is True


def test_log_filter_masks_sensitive_values_before_formatting():
    import logging
    from app.security import SensitiveDataFilter

    record = logging.LogRecord(
        "test",
        logging.INFO,
        __file__,
        1,
        "身份证=%s 手机=%s",
        ("110105199001011234", "13800138000"),
        None,
    )
    assert SensitiveDataFilter().filter(record) is True
    rendered = record.getMessage()
    assert "110105199001011234" not in rendered
    assert "13800138000" not in rendered
