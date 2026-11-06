from __future__ import annotations


def test_commercial_desktop_requires_current_policy_acceptance(
    client, monkeypatch, tmp_path
):
    monkeypatch.setenv("REQUIRE_COMPLIANCE_ACCEPTANCE", "1")
    monkeypatch.setenv("COMPLIANCE_CONSENT_FILE", str(tmp_path / "consent.json"))

    status = client.get("/api/system/compliance")
    blocked = client.get("/api/cases")
    accepted = client.post(
        "/api/system/compliance/accept",
        json={
            "terms_version": status.json()["data"]["versions"]["terms"],
            "privacy_version": status.json()["data"]["versions"]["privacy"],
            "ai_notice_version": status.json()["data"]["versions"]["ai_notice"],
            "accept_terms": True,
            "accept_sensitive_data_processing": True,
            "accept_ai_notice": True,
        },
    )
    allowed = client.get("/api/cases")
    withdrawn = client.delete("/api/system/compliance/consent")
    blocked_again = client.get("/api/cases")

    assert status.status_code == 200
    assert status.json()["data"]["acceptance_required"] is True
    assert blocked.status_code == 428
    assert blocked.json()["error"]["code"] == "POLICY_ACCEPTANCE_REQUIRED"
    assert accepted.status_code == 200
    assert accepted.json()["data"]["accepted"] is True
    assert allowed.status_code == 200
    assert withdrawn.status_code == 200
    assert blocked_again.status_code == 428


def test_data_export_and_deletion_remain_available_before_acceptance(
    client, monkeypatch, tmp_path
):
    monkeypatch.setenv("REQUIRE_COMPLIANCE_ACCEPTANCE", "1")
    monkeypatch.setenv("COMPLIANCE_CONSENT_FILE", str(tmp_path / "consent.json"))

    status = client.get("/api/system/data-management")
    clear = client.post(
        "/api/system/data/clear",
        json={"confirmation": "DELETE ALL CASES"},
    )

    assert status.status_code == 200
    assert clear.status_code == 200
