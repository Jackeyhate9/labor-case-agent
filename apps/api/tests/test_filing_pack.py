from __future__ import annotations

import zipfile
from pathlib import Path

from docx import Document as DocxDocument


def envelope(response, status=200):
    assert response.status_code == status, response.text
    body = response.json()
    assert body["success"] is True
    return body["data"]


def _docx_text(archive: zipfile.ZipFile, name: str, tmp_path: Path) -> str:
    path = tmp_path / Path(name).name
    path.write_bytes(archive.read(name))
    document = DocxDocument(path)
    cells = [cell.text for table in document.tables for row in table.rows for cell in row.cells]
    return "\n".join([*(p.text for p in document.paragraphs), *cells])


def test_filing_pack_prefills_known_case_data_and_keeps_unknowns_explicit(client, tmp_path):
    case = envelope(
        client.post(
            "/api/cases",
            json={
                "title": "线下立案测试案件",
                "jurisdiction_region": "北京市朝阳区",
                "employment_start_date": "2024-03-01",
                "parties": [
                    {"party_type": "worker", "name": "张三"},
                    {"party_type": "company", "name": "北京示例科技有限公司"},
                ],
            },
        ),
        201,
    )
    envelope(
        client.post(
            f"/api/cases/{case['id']}/claims",
            json={"claim_type": "wage_arrears", "title": "支付拖欠工资", "amount": "5000.00"},
        ),
        201,
    )
    envelope(
        client.post(
            f"/api/cases/{case['id']}/evidence",
            files={"file": ("工资转账记录.txt", "2026年1月转账1000元".encode(), "text/plain")},
        ),
        201,
    )

    exported = envelope(client.post(f"/api/cases/{case['id']}/filing-pack"))
    path = Path(exported["path"])
    assert path.name == "offline-filing-pack.zip"
    assert path.stat().st_size == exported["size"] > 0

    with zipfile.ZipFile(path) as archive:
        expected = {
            "01-劳动仲裁申请书-预填版.docx",
            "02-送达地址确认书-预填版.docx",
            "03-证据材料清单-预填版.docx",
            "04-案件审理要素表-预填版.docx",
            "05-线下办理核对清单.docx",
            "README-来源与适用范围.txt",
        }
        assert expected == set(archive.namelist())
        application = _docx_text(archive, "01-劳动仲裁申请书-预填版.docx", tmp_path)
        assert "张三" in application
        assert "北京示例科技有限公司" in application
        assert "支付拖欠工资：5000.00元" in application
        assert "[请本人填写]" in application

        catalog = _docx_text(archive, "03-证据材料清单-预填版.docx", tmp_path)
        assert "EV-001" in catalog and "工资转账记录.txt" in catalog

        checklist = _docx_text(archive, "05-线下办理核对清单.docx", tmp_path)
        assert "通常申请书一式四份" in checklist
        assert "以拟提交仲裁机构最新要求为准" in checklist

        readme = archive.read("README-来源与适用范围.txt").decode("utf-8")
        assert "北京市朝阳区劳动人事争议仲裁委员会" in readme
        assert "不构成正式法律意见" in readme


def test_filing_pack_never_uses_unconfirmed_facts(client, case_id, tmp_path):
    evidence = envelope(
        client.post(
            f"/api/cases/{case_id}/evidence",
            files={"file": ("待核实.txt", "公司承诺赔偿999999元".encode(), "text/plain")},
        ),
        201,
    )
    envelope(client.post(f"/api/evidence/{evidence['id']}/process"))

    exported = envelope(client.post(f"/api/cases/{case_id}/filing-pack"))
    with zipfile.ZipFile(Path(exported["path"])) as archive:
        application = _docx_text(archive, "01-劳动仲裁申请书-预填版.docx", tmp_path)
        assert "999999" not in application
        assert "仅使用用户已确认事实" in application
