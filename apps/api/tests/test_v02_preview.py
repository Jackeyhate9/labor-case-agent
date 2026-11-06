import csv
import io

import pytest
from docx import Document as DocxDocument
from openpyxl import Workbook


def envelope(response, status=200):
    assert response.status_code == status, response.text
    payload = response.json()
    assert payload["success"] is True
    return payload["data"]


def upload(client, case_id, filename, content, mime="application/octet-stream"):
    return envelope(
        client.post(
            f"/api/cases/{case_id}/evidence",
            files={"file": (filename, content, mime)},
        ),
        201,
    )


def test_docx_preview_is_derived_html_and_escapes_active_markup(client, case_id, monkeypatch):
    from app import services

    monkeypatch.setattr(services, "MAX_UPLOAD_BYTES", 2 * 1024 * 1024)
    stream = io.BytesIO()
    doc = DocxDocument()
    doc.add_heading("工资记录", level=1)
    doc.add_paragraph("<script>alert('x')</script>")
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "期间"
    table.rows[0].cells[1].text = "金额"
    doc.save(stream)
    evidence = upload(client, case_id, "record.docx", stream.getvalue())

    preview = envelope(client.get(f"/api/evidence/{evidence['id']}/preview/data"))
    assert preview["kind"] == "document"
    assert "工资记录" in preview["html"]
    assert "<script>" not in preview["html"]
    assert "&lt;script&gt;" in preview["html"]
    assert preview["derived"] is True


@pytest.mark.parametrize("kind", ["csv", "xlsx"])
def test_spreadsheet_preview_returns_bounded_rows(client, case_id, monkeypatch, kind):
    from app import services

    monkeypatch.setattr(services, "MAX_UPLOAD_BYTES", 2 * 1024 * 1024)
    if kind == "csv":
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(["期间", "应发", "实付"])
        writer.writerow(["2026-02", "6000", "1000"])
        content = stream.getvalue().encode("utf-8-sig")
    else:
        binary = io.BytesIO()
        workbook = Workbook()
        workbook.active.append(["期间", "应发", "实付"])
        workbook.active.append(["2026-02", 6000, 1000])
        workbook.save(binary)
        content = binary.getvalue()
    evidence = upload(client, case_id, f"wages.{kind}", content)

    preview = envelope(client.get(f"/api/evidence/{evidence['id']}/preview/data"))
    assert preview["kind"] == "table"
    assert preview["sheets"][0]["rows"][0] == ["期间", "应发", "实付"]
    assert preview["sheets"][0]["rows"][1] == ["2026-02", "6000", "1000"]
    assert preview["truncated"] is False


def test_original_content_requires_the_case_owner(client, case_id):
    evidence = upload(client, case_id, "note.txt", b"private evidence", "text/plain")
    denied = client.get(
        f"/api/evidence/{evidence['id']}/content",
        headers={"X-Owner-ID": "different-local-user"},
    )
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "EVIDENCE_NOT_FOUND"
