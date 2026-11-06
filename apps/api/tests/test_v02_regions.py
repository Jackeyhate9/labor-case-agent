from pathlib import Path
import hashlib
import io

import pytest
from PIL import Image
from reportlab.pdfgen import canvas


DEMO = Path(__file__).resolve().parents[3] / "samples" / "demo-case"


def envelope(response, status=200):
    assert response.status_code == status, response.text
    payload = response.json()
    assert payload["success"] is True
    return payload["data"]


def test_processed_image_exposes_clickable_ocr_regions(client, case_id, monkeypatch):
    pytest.importorskip("rapidocr_onnxruntime")
    from app import services

    monkeypatch.setattr(services, "MAX_UPLOAD_BYTES", 2 * 1024 * 1024)
    image = (DEMO / "chat-01.png").read_bytes()
    evidence = envelope(
        client.post(
            f"/api/cases/{case_id}/evidence",
            files={"file": ("chat-01.png", image, "image/png")},
        ),
        201,
    )

    envelope(client.post(f"/api/evidence/{evidence['id']}/process"))
    ocr = envelope(client.get(f"/api/evidence/{evidence['id']}/ocr"))

    page = ocr["pages"][0]
    assert page["width"] > 0 and page["height"] > 0
    assert page["regions"]
    salary = next(region for region in page["regions"] if "6000" in region["raw_text"])
    assert salary["evidence_page_id"] == page["id"]
    assert salary["bbox_width"] > 0 and salary["bbox_height"] > 0
    assert 0 <= salary["bbox_x"] < page["width"]
    assert 0 <= salary["bbox_y"] < page["height"]
    assert salary["confidence"] is not None
    assert salary["created_at"]


def test_image_fact_links_back_to_the_exact_ocr_region(client, case_id, monkeypatch):
    pytest.importorskip("rapidocr_onnxruntime")
    from app import services

    monkeypatch.setattr(services, "MAX_UPLOAD_BYTES", 2 * 1024 * 1024)
    image = (DEMO / "chat-01.png").read_bytes()
    evidence = envelope(
        client.post(
            f"/api/cases/{case_id}/evidence",
            files={"file": ("chat-01.png", image, "image/png")},
        ),
        201,
    )

    processed = envelope(client.post(f"/api/evidence/{evidence['id']}/process"))
    salary_fact = next(fact for fact in processed["candidate_facts"] if "6000" in fact["source_quote"])
    assert salary_fact["source_region_id"]

    ocr = envelope(client.get(f"/api/evidence/{evidence['id']}/ocr"))
    region = next(
        region
        for page in ocr["pages"]
        for region in page["regions"]
        if region["id"] == salary_fact["source_region_id"]
    )
    assert region["raw_text"] == salary_fact["source_quote"]


def test_image_preview_and_region_crop_never_modify_the_original(client, case_id, monkeypatch):
    pytest.importorskip("rapidocr_onnxruntime")
    from app import services

    monkeypatch.setattr(services, "MAX_UPLOAD_BYTES", 2 * 1024 * 1024)
    original = (DEMO / "chat-01.png").read_bytes()
    original_hash = hashlib.sha256(original).hexdigest()
    evidence = envelope(
        client.post(
            f"/api/cases/{case_id}/evidence",
            files={"file": ("chat-01.png", original, "image/png")},
        ),
        201,
    )
    envelope(client.post(f"/api/evidence/{evidence['id']}/process"))

    preview = envelope(client.get(f"/api/evidence/{evidence['id']}/preview"))
    assert preview["kind"] == "image"
    assert preview["content_url"].endswith(f"/api/evidence/{evidence['id']}/content")
    content = client.get(preview["content_url"])
    assert content.status_code == 200
    assert hashlib.sha256(content.content).hexdigest() == original_hash

    ocr = envelope(client.get(f"/api/evidence/{evidence['id']}/ocr"))
    region = next(r for r in ocr["pages"][0]["regions"] if "6000" in r["raw_text"])
    crop = client.get(f"/api/regions/{region['id']}/crop")
    assert crop.status_code == 200
    assert crop.headers["content-type"] == "image/png"
    with Image.open(io.BytesIO(crop.content)) as cropped:
        assert cropped.width > 0 and cropped.height > 0

    content_after = client.get(preview["content_url"])
    assert hashlib.sha256(content_after.content).hexdigest() == original_hash


def test_pdf_ocr_regions_keep_page_and_coordinate_location(client, case_id, monkeypatch):
    from app import services

    monkeypatch.setattr(services, "MAX_UPLOAD_BYTES", 2 * 1024 * 1024)
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(400, 600))
    pdf.drawString(72, 500, "salary arrears 6000")
    pdf.showPage()
    pdf.drawString(72, 400, "second page")
    pdf.save()
    evidence = envelope(
        client.post(
            f"/api/cases/{case_id}/evidence",
            files={"file": ("contract.pdf", buffer.getvalue(), "application/pdf")},
        ),
        201,
    )

    envelope(client.post(f"/api/evidence/{evidence['id']}/process"))
    ocr = envelope(client.get(f"/api/evidence/{evidence['id']}/ocr"))
    assert len(ocr["pages"]) == 2
    first = ocr["pages"][0]
    assert first["page_number"] == 1
    assert first["width"] == 400 and first["height"] == 600
    amount = next(region for region in first["regions"] if region["raw_text"] == "6000")
    assert amount["bbox_x"] > 0 and amount["bbox_y"] > 0

    crop = client.get(f"/api/regions/{amount['id']}/crop")
    assert crop.status_code == 200
    with Image.open(io.BytesIO(crop.content)) as cropped:
        assert cropped.width > 0 and cropped.height > 0
