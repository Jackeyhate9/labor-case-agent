from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import shutil
import uuid
import zipfile
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from docx import Document as DocxDocument
from openpyxl import Workbook, load_workbook
from pypdf import PdfReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models
from .app_paths import app_data_root
from .filing_pack import create_filing_pack
from .providers.ocr import OCRPageResult, OCRRegionResult, OCRRouter
from .security import validate_no_executable_disguise, validate_safe_extension


BASE_DIR = Path(__file__).resolve().parents[1]
STORAGE_ROOT = Path(os.getenv("STORAGE_ROOT", app_data_root() / "cases")).resolve()
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 20 * 1024 * 1024))
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".pdf", ".docx", ".txt", ".csv", ".xlsx", ".mp3", ".wav", ".m4a", ".mp4"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


class ServiceError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def row_dict(row: Any) -> dict[str, Any]:
    return {c.name: jsonable(getattr(row, c.name)) for c in row.__table__.columns}


def safe_case_dir(case_id: str, part: str) -> Path:
    if not re.fullmatch(r"[0-9a-f-]{36}", case_id):
        raise ServiceError("INVALID_CASE_ID", "Invalid case identifier")
    root = STORAGE_ROOT.resolve()
    result = (root / case_id / part).resolve()
    if root != result and root not in result.parents:
        raise ServiceError("PATH_TRAVERSAL", "Unsafe storage path")
    result.mkdir(parents=True, exist_ok=True)
    return result


def validate_upload(filename: str, content: bytes) -> str:
    if not filename or Path(filename).name != filename or ".." in filename:
        raise ServiceError("PATH_TRAVERSAL", "Unsafe filename")
    ext = Path(filename).suffix.lower()
    # v0.2 calls out executable disguise chains distinctly, while a plain
    # unsupported extension retains the v0.1 UNSUPPORTED_FILE_TYPE code.
    if len(Path(filename).suffixes) > 1:
        validate_safe_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ServiceError("UNSUPPORTED_FILE_TYPE", f"Unsupported extension: {ext}")
    # Preserve the v0.1 public error contract for unsupported extensions;
    # deeper disguise checks still protect extensions accepted by the API.
    validate_safe_extension(filename)
    if len(content) > MAX_UPLOAD_BYTES:
        raise ServiceError("FILE_TOO_LARGE", f"Maximum upload size is {MAX_UPLOAD_BYTES} bytes", 413)
    if not content:
        raise ServiceError("EMPTY_FILE", "Empty files are not accepted")
    validate_no_executable_disguise(content)
    return ext


def save_upload(db: Session, case: models.Case, filename: str, mime: str, content: bytes) -> tuple[models.Evidence, bool]:
    ext = validate_upload(filename, content)
    digest = hashlib.sha256(content).hexdigest()
    duplicate = db.scalar(select(models.Evidence).where(models.Evidence.case_id == case.id, models.Evidence.sha256 == digest))
    if duplicate:
        return duplicate, True
    count = db.scalar(select(func.count()).select_from(models.Evidence).where(models.Evidence.case_id == case.id)) or 0
    ev = models.Evidence(
        case_id=case.id,
        evidence_number=f"EV-{count + 1:03d}",
        original_filename=filename,
        stored_filename=f"{digest}{ext}",
        mime_type=mime or "application/octet-stream",
        sha256=digest,
        file_size=len(content),
    )
    target = safe_case_dir(case.id, "original") / ev.stored_filename
    target.write_bytes(content)
    db.add(ev)
    db.flush()
    db.add(models.AuditLog(case_id=case.id, action="evidence.upload", entity_type="evidence", entity_id=ev.id, details=json.dumps({"sha256": digest})))
    return ev, False


def parse_document_with_regions(path: Path) -> tuple[list[OCRPageResult], str, str | None, list[str]]:
    ext = path.suffix.lower()
    try:
        if ext == ".txt":
            return [OCRPageResult(path.read_text(encoding="utf-8-sig"))], "text-parser", None, []
        if ext == ".csv":
            text = path.read_text(encoding="utf-8-sig")
            rows = list(csv.reader(io.StringIO(text)))
            return [OCRPageResult("\n".join(" | ".join(cell for cell in row) for row in rows))], "csv-parser", None, []
        if ext == ".docx":
            doc = DocxDocument(path)
            return [OCRPageResult("\n".join(p.text for p in doc.paragraphs))], "python-docx", None, []
        if ext == ".pdf":
            reader = PdfReader(path)
            try:
                import fitz

                document = fitz.open(path)
                parsed: list[OCRPageResult] = []
                for index, pdf_page in enumerate(document):
                    regions = []
                    for word in pdf_page.get_text("words"):
                        x0, y0, x1, y1, raw_text = word[:5]
                        regions.append(
                            OCRRegionResult(
                                raw_text=str(raw_text),
                                normalized_text=str(raw_text).strip(),
                                confidence=None,
                                bbox_x=float(x0),
                                bbox_y=float(y0),
                                bbox_width=float(x1 - x0),
                                bbox_height=float(y1 - y0),
                            )
                        )
                    parsed.append(
                        OCRPageResult(
                            text=reader.pages[index].extract_text() or "",
                            width=round(pdf_page.rect.width),
                            height=round(pdf_page.rect.height),
                            regions=regions,
                        )
                    )
                document.close()
                return parsed, "pypdf", None, []
            except ImportError:
                return [OCRPageResult(page.extract_text() or "") for page in reader.pages], "pypdf", "PyMuPDF is unavailable; PDF coordinate regions were not generated", []
        if ext == ".xlsx":
            wb = load_workbook(path, read_only=True, data_only=True)
            pages = []
            for ws in wb.worksheets:
                pages.append("\n".join(" | ".join("" if v is None else str(v) for v in row) for row in ws.iter_rows(values_only=True)))
            return [OCRPageResult(text) for text in pages], "openpyxl", None, []
        if ext in IMAGE_EXTENSIONS:
            result = OCRRouter().recognize_image(path)
            return result.pages, result.provider, result.warning, result.fallback_reasons
    except Exception as exc:
        raise ServiceError("DOCUMENT_PARSE_FAILED", f"Document parsing failed: {type(exc).__name__}", 422) from exc
    raise ServiceError("UNSUPPORTED_FILE_TYPE", "Unsupported document type")


def parse_document(path: Path) -> tuple[list[str], str, str | None]:
    """v0.1-compatible parser interface; richer callers use parse_document_with_regions."""
    pages, engine, warning, _ = parse_document_with_regions(path)
    return [page.text for page in pages], engine, warning


DATE_RE = re.compile(r"(?P<year>20\d{2})[年/-](?P<month>0?[1-9]|1[0-2])(?:[月/-](?P<day>0?[1-9]|[12]\d|3[01])日?)?")
AMOUNT_RE = re.compile(r"(?<!\d)(\d+(?:\.\d{1,2})?)\s*元")


def extract_candidate_facts(db: Session, ev: models.Evidence, pages: list[models.EvidencePage]) -> list[models.ExtractedFact]:
    created: list[models.ExtractedFact] = []
    keywords = {
        "工资": "salary_agreement",
        "转账": "salary_payment",
        "欠薪": "salary_arrears",
        "社保": "social_insurance",
        "入职": "employment_start",
        "离职": "employment_end",
        "解除": "termination_notice",
        "安排": "management_instruction",
    }
    for page in pages:
        for line in filter(None, (x.strip() for x in page.ocr_text.splitlines())):
            fact_type = next((kind for key, kind in keywords.items() if key in line), None)
            dates = list(DATE_RE.finditer(line))
            amounts = list(AMOUNT_RE.finditer(line))
            if not (fact_type or dates or amounts):
                continue
            date_value = None
            precision = None
            if dates:
                m = dates[0]
                precision = "day" if m.group("day") else "month"
                date_value = date(int(m.group("year")), int(m.group("month")), int(m.group("day") or 1))
            amount = Decimal(amounts[0].group(1)) if amounts else None
            fact = models.ExtractedFact(
                case_id=ev.case_id,
                fact_type=fact_type or ("salary_payment" if amount else "other"),
                object_value=line,
                normalized_value=line,
                date_value=date_value,
                date_precision=precision,
                amount_value=amount,
                source_evidence_id=ev.id,
                source_page=page.page_number,
                source_region_id=next((region.id for region in page.regions if region.raw_text.strip() == line), None),
                source_quote=line,
                extraction_method="deterministic_rule",
                machine_confidence=Decimal("0.70"),
                review_status="machine_extracted",
            )
            db.add(fact)
            created.append(fact)
    db.flush()
    # Mark contradictory machine extractions for human resolution. Confidence is
    # deliberately advisory; no conflicting candidate is promoted automatically.
    by_key: dict[tuple[str, date | None], list[models.ExtractedFact]] = {}
    for fact in created:
        by_key.setdefault((fact.fact_type, fact.date_value), []).append(fact)
    for group in by_key.values():
        values = {(f.normalized_value, str(f.amount_value)) for f in group}
        if len(group) > 1 and len(values) > 1:
            conflict_id = str(uuid.uuid4())
            for fact in group:
                fact.review_status = "conflicted"
                fact.conflict_group_id = conflict_id
    return created


def process_evidence(db: Session, ev: models.Evidence) -> dict[str, Any]:
    path = safe_case_dir(ev.case_id, "original") / ev.stored_filename
    if not path.exists():
        raise ServiceError("FILE_MISSING", "Stored evidence file is missing", 404)
    db.query(models.ExtractedFact).filter(models.ExtractedFact.source_evidence_id == ev.id).delete()
    db.query(models.EvidencePage).filter(models.EvidencePage.evidence_id == ev.id).delete()
    parsed_pages, engine, warning, fallback_reasons = parse_document_with_regions(path)
    pages = []
    for number, parsed in enumerate(parsed_pages, 1):
        page = models.EvidencePage(
            evidence_id=ev.id,
            page_number=number,
            ocr_text=parsed.text,
            ocr_engine=engine,
            width=parsed.width,
            height=parsed.height,
        )
        db.add(page)
        db.flush()
        for region in parsed.regions:
            db.add(models.EvidenceRegion(
                evidence_page_id=page.id,
                region_type=region.region_type,
                bounding_box=json.dumps([region.bbox_x, region.bbox_y, region.bbox_width, region.bbox_height]),
                bbox_x=Decimal(str(region.bbox_x)),
                bbox_y=Decimal(str(region.bbox_y)),
                bbox_width=Decimal(str(region.bbox_width)),
                bbox_height=Decimal(str(region.bbox_height)),
                raw_text=region.raw_text,
                normalized_text=region.normalized_text,
                confidence=region.confidence,
            ))
        pages.append(page)
    db.flush()
    facts = extract_candidate_facts(db, ev, pages)
    ev.page_count = len(pages)
    ev.processing_status = "completed" if not warning else "degraded"
    ev.ocr_status = "completed" if engine == "rapidocr" and not warning else ("not_required" if engine != "unavailable" else "failed")
    db.add(models.AuditLog(case_id=ev.case_id, action="evidence.process", entity_type="evidence", entity_id=ev.id, details=json.dumps({"engine": engine, "warning": warning, "fallback_reasons": fallback_reasons})))
    return {"evidence": row_dict(ev), "pages": [row_dict(p) for p in pages], "candidate_facts": [row_dict(f) for f in facts], "warning": warning, "fallback_reasons": fallback_reasons}


def rebuild_timeline(db: Session, case_id: str) -> list[models.TimelineEvent]:
    db.query(models.TimelineEvent).filter(models.TimelineEvent.case_id == case_id).delete()
    facts = db.scalars(select(models.ExtractedFact).where(models.ExtractedFact.case_id == case_id, models.ExtractedFact.review_status == "user_confirmed")).all()
    seen: set[tuple[Any, ...]] = set()
    result = []
    for fact in facts:
        key = (fact.date_value, fact.fact_type, fact.user_corrected_value or fact.normalized_value or fact.object_value)
        if key in seen:
            continue
        seen.add(key)
        event = models.TimelineEvent(case_id=case_id, event_date=fact.date_value, date_precision=fact.date_precision, event_type=fact.fact_type, title=fact.predicate, description=key[2], source_fact_id=fact.id, source_evidence_id=fact.source_evidence_id)
        db.add(event)
        result.append(event)
    db.flush()
    return result


def payment_total(wage: models.WageEntry) -> Decimal:
    try:
        payments = json.loads(wage.payments_json or "[]")
        if payments:
            return sum((Decimal(str(p.get("amount", "0"))) for p in payments), Decimal("0"))
    except (ValueError, TypeError, json.JSONDecodeError):
        pass
    return Decimal(wage.paid_amount or 0)


def wage_summary(wages: list[models.WageEntry]) -> dict[str, str]:
    expected = sum((Decimal(w.expected_amount) for w in wages), Decimal("0"))
    paid = sum((payment_total(w) for w in wages), Decimal("0"))
    arrears = max(expected - paid, Decimal("0"))
    q = Decimal("0.01")
    return {"expected": format(expected.quantize(q, rounding=ROUND_HALF_UP), "f"), "paid": format(paid.quantize(q, rounding=ROUND_HALF_UP), "f"), "arrears": format(arrears.quantize(q, rounding=ROUND_HALF_UP), "f")}


def compensation_summary(case: models.Case, wages: list[models.WageEntry]) -> dict[str, Any]:
    """Deterministic preliminary estimate; legal applicability remains user-reviewed."""
    if not case.employment_start_date or not case.employment_end_date or not wages:
        return {"status": "missing_inputs", "amount": None, "service_months": None, "compensation_months": None, "warning": "需补充并复核入离职日期及月工资基数"}
    start, end = case.employment_start_date, case.employment_end_date
    if end < start:
        return {"status": "invalid_inputs", "amount": None, "service_months": None, "compensation_months": None, "warning": "离职日期早于入职日期"}
    service_months = max((end.year - start.year) * 12 + end.month - start.month, 0)
    full_years, remainder = divmod(service_months, 12)
    compensation_months = Decimal(full_years) + (Decimal("1") if remainder >= 6 else Decimal("0.5") if remainder else Decimal("0"))
    average = sum((Decimal(w.expected_amount) for w in wages), Decimal("0")) / Decimal(len(wages))
    amount = (average * compensation_months).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"status": "preliminary", "amount": format(amount, "f"), "service_months": service_months, "compensation_months": format(compensation_months, "f"), "average_monthly_wage": format(average.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f"), "warning": "仅为确定性函数初算，不代表经济补偿必然成立，适用前提须人工复核"}


DISCLAIMER = "本系统仅提供材料整理、信息提取、计算辅助和文书草稿，不构成正式法律意见。"


def generate_document(db: Session, case: models.Case, document_type: str) -> models.Document:
    facts = db.scalars(select(models.ExtractedFact).where(models.ExtractedFact.case_id == case.id, models.ExtractedFact.review_status == "user_confirmed")).all()
    wages = db.scalars(select(models.WageEntry).where(models.WageEntry.case_id == case.id)).all()
    claims = db.scalars(select(models.Claim).where(models.Claim.case_id == case.id)).all()
    version = (db.scalar(select(func.max(models.Document.version)).where(models.Document.case_id == case.id, models.Document.document_type == document_type)) or 0) + 1
    lines = [f"# {case.title} - {document_type}", "", DISCLAIMER, "", "## 已确认事实"]
    sources = []
    for fact in facts:
        value = fact.user_corrected_value or fact.normalized_value or fact.object_value
        source = f"{fact.source_evidence_id or 'manual'} / 第{fact.source_page or '-'}页"
        lines.append(f"- {value}（来源：{source}）")
        sources.append({"fact_id": fact.id, "evidence_id": fact.source_evidence_id, "page": fact.source_page})
    if not facts:
        lines.append("- [待用户确认事实]")
    if document_type in {"arbitration_application", "wage_schedule", "case_summary"}:
        summary = wage_summary(wages)
        lines.extend(["", "## 工资计算", f"- 应付：{summary['expected']} 元", f"- 已付：{summary['paid']} 元", f"- 欠付：{summary['arrears']} 元"])
    if claims:
        lines.extend(["", "## 请求", *[f"- {c.title}" for c in claims]])
    doc = models.Document(case_id=case.id, document_type=document_type, version=version, title=f"{case.title}-{document_type}-v{version}", content_markdown="\n".join(lines), sources_json=json.dumps(sources, ensure_ascii=False))
    db.add(doc)
    db.flush()
    return doc


def export_document(doc: models.Document, fmt: str) -> Path:
    out = safe_case_dir(doc.case_id, "exports") / f"{doc.document_type}-v{doc.version}.{fmt}"
    if fmt == "md":
        out.write_text(doc.content_markdown, encoding="utf-8")
    elif fmt == "json":
        out.write_text(json.dumps({"document": row_dict(doc), "sources": json.loads(doc.sources_json)}, ensure_ascii=False, indent=2), encoding="utf-8")
    elif fmt == "docx":
        d = DocxDocument()
        for line in doc.content_markdown.splitlines():
            d.add_paragraph(line.lstrip("#- "))
        d.save(out)
    elif fmt == "pdf":
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        c = canvas.Canvas(str(out))
        c.setFont("STSong-Light", 10)
        y = 810
        for line in doc.content_markdown.splitlines():
            if y < 40:
                c.showPage(); c.setFont("STSong-Light", 10); y = 810
            c.drawString(40, y, line[:90]); y -= 15
        c.save()
    else:
        raise ServiceError("UNSUPPORTED_EXPORT_FORMAT", "Document export supports md, json, docx and pdf")
    return out


def _write_docx(path: Path, title: str, sections: list[tuple[str, list[str]]]) -> None:
    """Create a restrained Chinese DOCX from already-reviewed structured data."""
    document = DocxDocument()
    document.add_heading(title, 0)
    document.add_paragraph(DISCLAIMER)
    for heading, lines in sections:
        document.add_heading(heading, level=1)
        if not lines:
            document.add_paragraph("[暂无已确认内容]")
        for line in lines:
            document.add_paragraph(line, style="List Bullet")
    document.save(path)


def _style_sheet(ws: Any, widths: list[int]) -> None:
    from openpyxl.styles import Alignment, Font, PatternFill

    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="173F5F")
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"
    ws.sheet_view.showGridLines = False
    for index, width in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + index)].width = width
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_case(db: Session, case: models.Case, fmt: str) -> Path:
    exports = safe_case_dir(case.id, "exports")
    facts = db.scalars(select(models.ExtractedFact).where(models.ExtractedFact.case_id == case.id)).all()
    wages = db.scalars(select(models.WageEntry).where(models.WageEntry.case_id == case.id)).all()
    evidence = db.scalars(select(models.Evidence).where(models.Evidence.case_id == case.id)).all()
    if fmt == "csv":
        out = exports / "wages.csv"
        with out.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=["period", "expected_amount", "paid_amount", "arrears", "payer", "payer_relationship"]); writer.writeheader()
            for w in wages:
                paid = payment_total(w); writer.writerow({"period": w.period, "expected_amount": w.expected_amount, "paid_amount": paid, "arrears": max(Decimal(w.expected_amount)-paid, Decimal("0")), "payer": w.payer, "payer_relationship": w.payer_relationship})
        return out
    if fmt == "xlsx":
        out = exports / "case.xlsx"; wb = Workbook(); ws = wb.active; ws.title = "wages"; ws.append(["period", "expected", "paid", "arrears", "payer"])
        for w in wages:
            paid = payment_total(w); ws.append([w.period, float(w.expected_amount), float(paid), float(max(Decimal(w.expected_amount)-paid, Decimal("0"))), w.payer])
        wb.save(out); return out
    if fmt == "json":
        out = exports / "case.json"; out.write_text(json.dumps({"case": row_dict(case), "evidence": [row_dict(x) for x in evidence], "facts": [row_dict(x) for x in facts], "wages": [row_dict(x) for x in wages]}, ensure_ascii=False, indent=2), encoding="utf-8"); return out
    if fmt != "zip":
        raise ServiceError("UNSUPPORTED_EXPORT_FORMAT", "Case export supports zip, json, csv and xlsx")
    confirmed = [f for f in facts if f.review_status == "user_confirmed"]
    timeline = db.scalars(
        select(models.TimelineEvent)
        .where(models.TimelineEvent.case_id == case.id)
        .order_by(models.TimelineEvent.event_date, models.TimelineEvent.id)
    ).all()
    claims = db.scalars(select(models.Claim).where(models.Claim.case_id == case.id)).all()
    stage = exports / "case-export"
    if stage.exists():
        shutil.rmtree(stage)
    for relative in ["evidence", "extracted/ocr", "audit"]:
        (stage / relative).mkdir(parents=True, exist_ok=True)

    # The v0.2 archive is richer, but retains the three root entries promised
    # by the v0.1 ZIP contract so existing consumers continue to work.
    for legacy_format in ("json", "csv", "xlsx"):
        legacy_path = export_case(db, case, legacy_format)
        shutil.copy2(legacy_path, stage / legacy_path.name)

    fact_lines = [
        f"{f.user_corrected_value or f.normalized_value or f.object_value}（来源：{f.source_evidence_id or '用户手动输入'} / 第{f.source_page or '-'}页）"
        for f in confirmed
    ]
    request_lines = [c.title for c in claims]
    summary = wage_summary(wages)
    readme = stage / "README-案件说明.md"
    readme.write_text(
        "\n".join(
            [
                f"# {case.title} - 案件档案包",
                "",
                DISCLAIMER,
                "",
                f"- 已确认事实：{len(confirmed)} 条",
                f"- 排除未确认/冲突/拒绝事实：{len(facts) - len(confirmed)} 条",
                f"- 证据：{len(evidence)} 份",
                f"- 欠付工资初算：{summary['arrears']} 元",
                "- 法律适用、时效、管辖及最终请求须人工复核。",
            ]
        ),
        encoding="utf-8",
    )

    _write_docx(stage / "01-案件事实摘要.docx", "案件事实摘要", [("已确认事实", fact_lines)])
    _write_docx(
        stage / "02-劳动仲裁申请书草稿.docx",
        "劳动仲裁申请书草稿",
        [("仲裁请求", request_lines), ("事实与理由（仅已确认事实）", fact_lines), ("金额初算", [f"拖欠工资：{summary['arrears']} 元"])],
    )
    fact_types = {f.fact_type for f in confirmed}
    gaps = []
    if "employment_start" not in fact_types:
        gaps.append("入职时间及来源证据仍需确认")
    if "salary_agreement" not in fact_types:
        gaps.append("工资标准证据仍需补充")
    if "salary_payment" not in fact_types:
        gaps.append("付款主体、转账备注和款项性质仍需核验")
    _write_docx(stage / "06-待补证清单.docx", "待补证清单", [("可执行补证建议", gaps)])

    evidence_book = Workbook()
    evidence_sheet = evidence_book.active
    evidence_sheet.title = "证据目录"
    evidence_sheet.append(["证据编号", "原文件名", "类型", "SHA-256", "处理状态", "证明目的（待用户填写）"])
    for ev in evidence:
        evidence_sheet.append([ev.evidence_number, ev.original_filename, ev.mime_type, ev.sha256, ev.processing_status, ""])
    _style_sheet(evidence_sheet, [12, 30, 18, 68, 14, 30])
    evidence_book.save(stage / "03-证据目录.xlsx")

    wage_book = Workbook()
    wage_sheet = wage_book.active
    wage_sheet.title = "欠薪明细"
    wage_sheet.append(["月份", "应发", "已发", "欠付", "付款人", "付款人与单位关系", "备注"])
    for wage in wages:
        paid = payment_total(wage)
        arrears = max(Decimal(wage.expected_amount) - paid, Decimal("0"))
        wage_sheet.append([wage.period, float(Decimal(wage.expected_amount)), float(paid), float(arrears), wage.payer, wage.payer_relationship, wage.notes])
    for column in ("B", "C", "D"):
        for cell in wage_sheet[column][1:]:
            cell.number_format = '¥#,##0.00'
    _style_sheet(wage_sheet, [12, 14, 14, 14, 20, 22, 30])
    wage_book.save(stage / "04-欠薪明细.xlsx")

    timeline_book = Workbook()
    timeline_sheet = timeline_book.active
    timeline_sheet.title = "案件时间线"
    timeline_sheet.append(["日期", "精度", "事件类型", "标题", "说明", "来源事实", "来源证据"])
    for event in timeline:
        timeline_sheet.append([jsonable(event.event_date), event.date_precision, event.event_type, event.title, event.description, event.source_fact_id, event.source_evidence_id])
    _style_sheet(timeline_sheet, [14, 12, 20, 24, 45, 38, 38])
    timeline_book.save(stage / "05-案件时间线.xlsx")

    (stage / "extracted" / "confirmed-facts.json").write_text(
        json.dumps([row_dict(f) for f in confirmed], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (stage / "extracted" / "timeline.json").write_text(
        json.dumps([row_dict(event) for event in timeline], ensure_ascii=False, indent=2), encoding="utf-8"
    )

    pages_by_evidence: dict[str, list[models.EvidencePage]] = {}
    for ev in evidence:
        pages_by_evidence[ev.id] = db.scalars(
            select(models.EvidencePage).where(models.EvidencePage.evidence_id == ev.id).order_by(models.EvidencePage.page_number)
        ).all()
        for page in pages_by_evidence[ev.id]:
            (stage / "extracted" / "ocr" / f"{ev.evidence_number}-page-{page.page_number:03d}.txt").write_text(page.ocr_text or "", encoding="utf-8")

    archive_entries: list[dict[str, Any]] = []
    for path in sorted(p for p in stage.rglob("*") if p.is_file()):
        relative = path.relative_to(stage).as_posix()
        archive_entries.append({"path": relative, "size": path.stat().st_size, "sha256": _sha256_file(path)})
    for ev in evidence:
        original = safe_case_dir(case.id, "original") / ev.stored_filename
        if original.exists():
            archive_entries.append({"path": f"evidence/{ev.evidence_number}-original{original.suffix.lower()}", "size": original.stat().st_size, "sha256": _sha256_file(original)})
    manifest_payload = {
        "case_id": case.id,
        "confirmed_fact_count": len(confirmed),
        "excluded_unconfirmed_fact_count": len(facts) - len(confirmed),
        "calculation": summary,
        "files": archive_entries,
        "disclaimer": DISCLAIMER,
    }
    manifest_path = stage / "audit" / "export-manifest.json"
    manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    out = exports / "case-archive.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(p for p in stage.rglob("*") if p.is_file()):
            archive.write(path, path.relative_to(stage).as_posix())
        for ev in evidence:
            original = safe_case_dir(case.id, "original") / ev.stored_filename
            if original.exists():
                archive.write(original, f"evidence/{ev.evidence_number}-original{original.suffix.lower()}", compress_type=zipfile.ZIP_STORED)
    return out


def export_filing_pack(db: Session, case: models.Case) -> Path:
    """Generate a locality-labelled, user-reviewable offline filing bundle."""
    output = create_filing_pack(db, case, safe_case_dir(case.id, "exports"))
    db.add(
        models.AuditLog(
            case_id=case.id,
            action="export_filing_pack",
            entity_type="case",
            entity_id=case.id,
            details=json.dumps({"filename": output.name, "confirmed_facts_only": True}, ensure_ascii=False),
        )
    )
    db.flush()
    return output


def delete_case_storage(case_id: str) -> None:
    root = STORAGE_ROOT.resolve()
    target = (root / case_id).resolve()
    if root not in target.parents:
        raise ServiceError("PATH_TRAVERSAL", "Unsafe deletion path")
    if target.exists():
        shutil.rmtree(target)
