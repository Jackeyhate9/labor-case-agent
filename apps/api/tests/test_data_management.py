from __future__ import annotations

from pathlib import Path

import pytest

from app import data_management

PASSPHRASE = "correct horse battery staple"


def test_encrypted_backup_restores_database_and_requires_api_key_reentry(
    client, case_id, monkeypatch, tmp_path
):
    monkeypatch.setenv("BACKUP_ROOT", str(tmp_path / "backups"))
    before = client.get(f"/api/cases/{case_id}").json()["data"]

    created = client.post(
        "/api/system/backups",
        json={"passphrase": PASSPHRASE},
    )
    assert created.status_code == 201
    backup = created.json()["data"]
    backup_path = Path(backup["path"])
    assert backup_path.read_bytes().startswith(b"LCA1")
    assert before["title"].encode("utf-8") not in backup_path.read_bytes()

    client.patch(f"/api/cases/{case_id}", json={"title": "已被修改"})
    with backup_path.open("rb") as handle:
        restored = client.post(
            "/api/system/restore",
            files={"file": (backup_path.name, handle, "application/octet-stream")},
            data={"passphrase": PASSPHRASE, "confirmation": "RESTORE"},
        )

    assert restored.status_code == 200
    assert restored.json()["data"]["api_key_reentry_required"] is True
    assert client.get(f"/api/cases/{case_id}").json()["data"]["title"] == before["title"]


def test_restore_rejects_wrong_passphrase_without_mutating_data(
    client, case_id, monkeypatch, tmp_path
):
    monkeypatch.setenv("BACKUP_ROOT", str(tmp_path / "backups"))
    backup = client.post(
        "/api/system/backups",
        json={"passphrase": PASSPHRASE},
    ).json()["data"]
    client.patch(f"/api/cases/{case_id}", json={"title": "保留这个标题"})

    with Path(backup["path"]).open("rb") as handle:
        response = client.post(
            "/api/system/restore",
            files={"file": ("backup.lca-backup", handle, "application/octet-stream")},
            data={"passphrase": "this is the wrong password", "confirmation": "RESTORE"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "BACKUP_DECRYPTION_FAILED"
    assert client.get(f"/api/cases/{case_id}").json()["data"]["title"] == "保留这个标题"


def test_clear_all_case_data_requires_explicit_confirmation(client, case_id):
    rejected = client.post(
        "/api/system/data/clear",
        json={"confirmation": "DELETE"},
    )
    accepted = client.post(
        "/api/system/data/clear",
        json={"confirmation": "DELETE ALL CASES"},
    )

    assert rejected.status_code == 422
    assert accepted.status_code == 200
    assert client.get("/api/cases").json()["data"] == []


def test_restore_rolls_back_database_when_file_swap_fails(
    client, case_id, monkeypatch, tmp_path
):
    monkeypatch.setenv("BACKUP_ROOT", str(tmp_path / "backups"))
    backup = client.post(
        "/api/system/backups",
        json={"passphrase": PASSPHRASE},
    ).json()["data"]
    client.patch(f"/api/cases/{case_id}", json={"title": "恢复失败后必须保留"})

    def fail_copytree(*_args, **_kwargs):
        raise OSError("simulated storage failure")

    monkeypatch.setattr(data_management.shutil, "copytree", fail_copytree)
    with Path(backup["path"]).open("rb") as handle, pytest.raises(OSError):
        client.post(
            "/api/system/restore",
            files={"file": ("backup.lca-backup", handle, "application/octet-stream")},
            data={"passphrase": PASSPHRASE, "confirmation": "RESTORE"},
        )

    assert (
        client.get(f"/api/cases/{case_id}").json()["data"]["title"]
        == "恢复失败后必须保留"
    )
