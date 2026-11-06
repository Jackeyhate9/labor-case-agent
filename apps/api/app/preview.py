from __future__ import annotations

import mimetypes
import csv
import html
import io
from pathlib import Path

from PIL import Image
from docx import Document as DocxDocument
from openpyxl import load_workbook

from . import models
from .services import ServiceError, safe_case_dir
from .security import redact_sensitive


def evidence_path(evidence: models.Evidence) -> Path:
    path = safe_case_dir(evidence.case_id, "original") / evidence.stored_filename
    if not path.is_file():
        raise ServiceError("FILE_MISSING", "Stored evidence file is missing", 404)
    return path


def content_type(evidence: models.Evidence) -> str:
    guessed, _ = mimetypes.guess_type(evidence.original_filename)
    return guessed or "application/octet-stream"


def preview_descriptor(evidence: models.Evidence) -> dict[str, object]:
    ext = Path(evidence.original_filename).suffix.lower()
    if ext in {".png", ".jpg", ".jpeg", ".webp"}:
        kind = "image"
    elif ext == ".pdf":
        kind = "pdf"
    elif ext == ".docx":
        kind = "document"
    elif ext in {".csv", ".xlsx"}:
        kind = "table"
    elif ext in {".mp3", ".wav", ".m4a", ".mp4"}:
        kind = "audio"
    else:
        kind = "text"
    return {
        "kind": kind,
        "content_url": f"/api/evidence/{evidence.id}/content",
        "original_filename": evidence.original_filename,
        "mime_type": content_type(evidence),
        "sha256": evidence.sha256,
        "derived": False,
    }


def preview_data(evidence: models.Evidence, max_rows: int = 200, max_columns: int = 50) -> dict[str, object]:
    path = evidence_path(evidence)
    ext = path.suffix.lower()
    descriptor = preview_descriptor(evidence)
    if ext == ".docx":
        document = DocxDocument(path)
        fragments: list[str] = []
        for paragraph in document.paragraphs:
            if not paragraph.text:
                continue
            level = 1 if paragraph.style and paragraph.style.name.startswith("Heading 1") else 2 if paragraph.style and paragraph.style.name.startswith("Heading") else None
            redacted, _ = redact_sensitive(paragraph.text)
            text = html.escape(redacted)
            fragments.append(f"<h{level}>{text}</h{level}>" if level else f"<p>{text}</p>")
        for table in document.tables:
            fragments.append("<table>")
            for row in table.rows[:max_rows]:
                fragments.append("<tr>" + "".join(f"<td>{html.escape(redact_sensitive(cell.text)[0])}</td>" for cell in row.cells[:max_columns]) + "</tr>")
            fragments.append("</table>")
        return {**descriptor, "html": "".join(fragments), "derived": True}
    if ext in {".csv", ".xlsx"}:
        sheets: list[dict[str, object]] = []
        truncated = False
        if ext == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                all_rows = list(csv.reader(stream))
            truncated = len(all_rows) > max_rows or any(len(row) > max_columns for row in all_rows[:max_rows])
            sheets.append({"name": "CSV", "rows": [[str(value) for value in row[:max_columns]] for row in all_rows[:max_rows]]})
        else:
            workbook = load_workbook(path, read_only=True, data_only=True)
            for sheet in workbook.worksheets:
                rows = []
                for index, row in enumerate(sheet.iter_rows(values_only=True)):
                    if index >= max_rows:
                        truncated = True
                        break
                    if len(row) > max_columns:
                        truncated = True
                    rows.append(["" if value is None else str(value) for value in row[:max_columns]])
                sheets.append({"name": sheet.title, "rows": rows})
            workbook.close()
        return {**descriptor, "sheets": sheets, "truncated": truncated, "derived": True}
    if ext in {".txt"}:
        raw = path.read_text(encoding="utf-8-sig")
        text, sensitive = redact_sensitive(raw)
        return {**descriptor, "text": text, "contains_sensitive_data": sensitive, "derived": True}
    return descriptor


def crop_region(evidence: models.Evidence, page: models.EvidencePage, region: models.EvidenceRegion) -> Path:
    if None in (region.bbox_x, region.bbox_y, region.bbox_width, region.bbox_height):
        raise ServiceError("REGION_COORDINATES_MISSING", "The OCR region has no coordinates", 409)
    source = evidence_path(evidence)
    target = safe_case_dir(evidence.case_id, "derived") / f"region-{region.id}.png"
    if source.suffix.lower() == ".pdf":
        import fitz

        document = fitz.open(source)
        try:
            pdf_page = document[page.page_number - 1]
            clip = fitz.Rect(
                float(region.bbox_x),
                float(region.bbox_y),
                float(region.bbox_x + region.bbox_width),
                float(region.bbox_y + region.bbox_height),
            )
            if clip.is_empty or not pdf_page.rect.intersects(clip):
                raise ServiceError("INVALID_REGION", "The OCR region is outside the source page", 422)
            pdf_page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip, alpha=False).save(target)
        finally:
            document.close()
        return target
    if source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ServiceError("REGION_CROP_UNSUPPORTED", "Region crop requires an image or PDF preview", 422)
    with Image.open(source) as image:
        x = max(int(float(region.bbox_x)), 0)
        y = max(int(float(region.bbox_y)), 0)
        right = min(int(float(region.bbox_x + region.bbox_width) + 1), image.width)
        bottom = min(int(float(region.bbox_y + region.bbox_height) + 1), image.height)
        if right <= x or bottom <= y:
            raise ServiceError("INVALID_REGION", "The OCR region is outside the source image", 422)
        image.crop((x, y, right, bottom)).convert("RGB").save(target, format="PNG")
    return target
