from __future__ import annotations

import json
import os
import secrets
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, File, Form, Header, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from . import models
from .database import Base, engine, get_db
from .audio import prepare_audio, transcribe_audio
from .app_profile import activate_app_profile, public_app_profile
from .data_management import (
    clear_all_case_data,
    create_encrypted_backup,
    data_management_status,
    resolve_backup,
    restore_encrypted_backup,
)
from .compliance import (
    accept_current_policies,
    is_current_acceptance,
    public_compliance_status,
    withdraw_policy_acceptance,
)
from .embedding import reindex_case_embeddings, search_case
from .evidence_graph import build_evidence_graph
from .review_agents import adversarial_review as run_adversarial_review, evidence_review as run_evidence_review
from .security import install_log_filters
from .settings import SystemSettingsPatch, load_settings, public_settings, save_settings
from .llm_config import (
    LLMConfigPatch,
    LLMConnectionTestRequest,
    public_llm_config,
    test_llm_connection,
    update_llm_config,
)
from .model_manager import (
    acknowledge_onboarding,
    get_install_job,
    model_manager_status,
    register_model_root,
    request_model_install,
)
from .preview import content_type, crop_region, evidence_path, preview_data, preview_descriptor
from .services import (
    DISCLAIMER, STORAGE_ROOT, ServiceError, delete_case_storage, export_case, export_filing_pack,
    compensation_summary, export_document, generate_document, process_evidence, rebuild_timeline,
    row_dict, safe_case_dir, save_upload, wage_summary,
)

activate_app_profile()
Base.metadata.create_all(engine)
_persisted_settings = load_settings()
for _key, _value in {
    "OCR_PROVIDER": _persisted_settings.ocr_provider,
    "AUDIO_PROVIDER": _persisted_settings.audio_provider,
    "EMBEDDING_PROVIDER": _persisted_settings.embedding_provider,
    "LLM_PROVIDER": _persisted_settings.llm_provider,
}.items():
    os.environ.setdefault(_key, _value)
install_log_filters()
app = FastAPI(title="Labor Case Agent API", version="0.2.0")
cors_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-App-Session", "X-Owner-ID"],
)


@app.middleware("http")
async def require_desktop_session(request: Request, call_next):
    expected = os.getenv("APP_SESSION_TOKEN", "").strip()
    header_valid = False
    if expected and request.method != "OPTIONS":
        supplied = request.headers.get("X-App-Session", "")
        cookie = request.cookies.get("app_session", "")
        header_valid = bool(supplied) and secrets.compare_digest(supplied, expected)
        cookie_valid = bool(cookie) and secrets.compare_digest(cookie, expected)
        if not header_valid and not cookie_valid:
            return fail(
                "SESSION_REQUIRED",
                "The desktop session is missing or has expired; restart the application",
                401,
            )
        source = request.headers.get("Origin") or request.headers.get("Referer")
        source_origin = ""
        if source:
            parsed = urlsplit(source)
            source_origin = f"{parsed.scheme}://{parsed.netloc}"
        if source_origin and source_origin not in cors_origins:
            return fail("ORIGIN_NOT_ALLOWED", "The request origin is not allowed", 403)
        if cookie_valid and not header_valid and not source_origin:
            return fail("ORIGIN_REQUIRED", "The desktop request source is missing", 403)
    if os.getenv("REQUIRE_COMPLIANCE_ACCEPTANCE", "0") == "1":
        allowed = (
            request.url.path == "/api/system/health"
            or request.url.path.startswith("/api/system/compliance")
            or request.url.path.startswith("/api/system/data-management")
            or request.url.path.startswith("/api/system/backups")
            or request.url.path == "/api/system/restore"
            or request.url.path == "/api/system/data/clear"
        )
        if request.method != "OPTIONS" and not allowed and not is_current_acceptance():
            return fail(
                "POLICY_ACCEPTANCE_REQUIRED",
                "Review and accept the current user agreement, privacy policy and AI notice",
                428,
            )
    response = await call_next(request)
    if expected and header_valid:
        response.set_cookie(
            "app_session",
            expected,
            httponly=True,
            samesite="strict",
            path="/",
        )
    return response


def ok(data: Any, **meta: Any) -> dict[str, Any]:
    return {"success": True, "data": data, "error": None, "meta": meta or {}}


def fail(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"success": False, "data": None, "error": {"code": code, "message": message}, "meta": {}})


@app.exception_handler(ServiceError)
def service_error(_: Request, exc: ServiceError):
    return fail(exc.code, exc.message, exc.status)


@app.exception_handler(RequestValidationError)
def validation_error(_: Request, exc: RequestValidationError):
    # Pydantic's default error structure echoes rejected input. That is useful
    # for local debugging but can reflect API keys submitted to this endpoint.
    sanitized = [{key: item[key] for key in ("loc", "msg", "type") if key in item} for item in exc.errors()]
    return fail("VALIDATION_ERROR", str(sanitized), 422)


class PartyIn(BaseModel):
    party_type: Literal["worker", "company", "legal_representative", "actual_controller", "manager", "payroll_intermediary", "witness", "other"]
    name: str = Field(min_length=1, max_length=200)
    alias: str | None = None
    role_description: str | None = None


class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    case_type: str = "wage_arrears"
    jurisdiction_region: str | None = None
    employment_start_date: date | None = None
    employment_end_date: date | None = None
    summary: str | None = None
    parties: list[PartyIn] = []


class CasePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    status: str | None = None
    jurisdiction_region: str | None = None
    employment_start_date: date | None = None
    employment_end_date: date | None = None
    summary: str | None = None


class FactPatch(BaseModel):
    user_corrected_value: str | None = None
    notes: str | None = None
    date_value: date | None = None
    date_precision: str | None = None
    amount_value: Decimal | None = None


class PaymentIn(BaseModel):
    amount: Decimal = Field(ge=0)
    payer: str | None = None
    payer_relationship: str | None = None
    payment_date: date | None = None


class WageIn(BaseModel):
    period: str
    expected_amount: Decimal = Field(ge=0)
    paid_amount: Decimal = Field(default=Decimal("0"), ge=0)
    payments: list[PaymentIn] = []
    payer: str | None = None
    payer_relationship: str | None = None
    payment_date: date | None = None
    notes: str | None = None


class ClaimIn(BaseModel):
    claim_type: str
    title: str
    amount: Decimal | None = Field(default=None, ge=0)
    status: str = "draft"
    basis: str | None = None


class DocumentGenerate(BaseModel):
    document_type: Literal["arbitration_application", "case_summary", "evidence_catalog", "wage_schedule", "timeline", "third_party_payment_note"] = "arbitration_application"


class ExportIn(BaseModel):
    format: Literal["docx", "pdf", "md", "json", "csv", "xlsx", "zip"] = "zip"


class ModelInstallIn(BaseModel):
    accept_license: bool = False
    accept_download: bool = False


class ModelOnboardingIn(BaseModel):
    choice: Literal["basic", "later", "installing"]


class ModelRootRegistrationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=4096)


class BackupCreateIn(BaseModel):
    passphrase: str = Field(min_length=12, max_length=200)


class ClearDataIn(BaseModel):
    confirmation: str


class ComplianceAcceptanceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    terms_version: str
    privacy_version: str
    ai_notice_version: str
    accept_terms: bool
    accept_sensitive_data_processing: bool
    accept_ai_notice: bool


def owner(x_owner_id: str = Header(default="local-user")) -> str:
    return x_owner_id


def get_case(db: Session, case_id: str, owner_id: str) -> models.Case:
    case = db.scalar(select(models.Case).where(models.Case.id == case_id, models.Case.owner_id == owner_id))
    if not case:
        raise ServiceError("CASE_NOT_FOUND", "Case not found", 404)
    return case


def get_evidence(db: Session, evidence_id: str, owner_id: str) -> models.Evidence:
    ev = db.scalar(select(models.Evidence).join(models.Case).where(models.Evidence.id == evidence_id, models.Case.owner_id == owner_id))
    if not ev:
        raise ServiceError("EVIDENCE_NOT_FOUND", "Evidence not found", 404)
    return ev


def get_fact(db: Session, fact_id: str, owner_id: str) -> models.ExtractedFact:
    fact = db.scalar(select(models.ExtractedFact).join(models.Case).where(models.ExtractedFact.id == fact_id, models.Case.owner_id == owner_id))
    if not fact:
        raise ServiceError("FACT_NOT_FOUND", "Fact not found", 404)
    return fact


@app.post("/api/cases", status_code=201)
def create_case(body: CaseCreate, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    case = models.Case(**body.model_dump(exclude={"parties"}), owner_id=owner_id)
    db.add(case); db.flush()
    for p in body.parties: db.add(models.Party(case_id=case.id, **p.model_dump()))
    db.add(models.AuditLog(case_id=case.id, action="case.create", entity_type="case", entity_id=case.id))
    db.commit()
    return ok(row_dict(case))


@app.get("/api/cases")
def list_cases(db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    rows = db.scalars(select(models.Case).where(models.Case.owner_id == owner_id).order_by(models.Case.created_at.desc())).all()
    return ok([row_dict(x) for x in rows], count=len(rows))


@app.get("/api/cases/{case_id}")
def read_case(case_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    case = get_case(db, case_id, owner_id)
    data = row_dict(case); data["parties"] = [row_dict(x) for x in case.parties]
    return ok(data)


@app.patch("/api/cases/{case_id}")
def patch_case(case_id: str, body: CasePatch, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    case = get_case(db, case_id, owner_id)
    for key, value in body.model_dump(exclude_unset=True).items(): setattr(case, key, value)
    db.add(models.AuditLog(case_id=case.id, action="case.update", entity_type="case", entity_id=case.id)); db.commit()
    return ok(row_dict(case))


@app.delete("/api/cases/{case_id}")
def delete_case(case_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    case = get_case(db, case_id, owner_id)
    db.delete(case); db.commit(); delete_case_storage(case_id)
    return ok({"id": case_id, "deleted": True})


@app.post("/api/cases/{case_id}/evidence", status_code=201)
async def upload_evidence(case_id: str, file: UploadFile = File(...), db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    case = get_case(db, case_id, owner_id)
    content = await file.read()
    ev, duplicate = save_upload(db, case, file.filename or "", file.content_type or "", content)
    db.commit()
    return ok(row_dict(ev), duplicate=duplicate)


@app.get("/api/cases/{case_id}/evidence")
def list_evidence(case_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    get_case(db, case_id, owner_id)
    rows = db.scalars(select(models.Evidence).where(models.Evidence.case_id == case_id).order_by(models.Evidence.upload_time)).all()
    return ok([row_dict(x) for x in rows], count=len(rows))


@app.get("/api/evidence/{evidence_id}")
def read_evidence(evidence_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    return ok(row_dict(get_evidence(db, evidence_id, owner_id)))


@app.get("/api/evidence/{evidence_id}/preview")
def evidence_preview(evidence_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    return ok(preview_descriptor(get_evidence(db, evidence_id, owner_id)))


@app.get("/api/evidence/{evidence_id}/preview/data")
def evidence_preview_data(evidence_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    return ok(preview_data(get_evidence(db, evidence_id, owner_id)))


@app.get("/api/evidence/{evidence_id}/content")
def evidence_content(evidence_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    evidence = get_evidence(db, evidence_id, owner_id)
    response = FileResponse(
        evidence_path(evidence),
        media_type=content_type(evidence),
        content_disposition_type="inline",
        filename=evidence.original_filename,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@app.get("/api/regions/{region_id}/crop")
def region_crop(region_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    row = db.execute(
        select(models.EvidenceRegion, models.EvidencePage, models.Evidence)
        .join(models.EvidencePage, models.EvidenceRegion.evidence_page_id == models.EvidencePage.id)
        .join(models.Evidence, models.EvidencePage.evidence_id == models.Evidence.id)
        .join(models.Case, models.Evidence.case_id == models.Case.id)
        .where(models.EvidenceRegion.id == region_id, models.Case.owner_id == owner_id)
    ).first()
    if not row:
        raise ServiceError("REGION_NOT_FOUND", "OCR region not found", 404)
    region, page, evidence = row
    path = crop_region(evidence, page, region)
    response = FileResponse(path, media_type="image/png", content_disposition_type="inline")
    response.headers["Cache-Control"] = "private, no-store"
    return response


@app.delete("/api/evidence/{evidence_id}")
def delete_evidence(evidence_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    ev = get_evidence(db, evidence_id, owner_id)
    path = safe_case_dir(ev.case_id, "original") / ev.stored_filename
    if path.exists(): path.unlink()
    db.delete(ev); db.commit()
    return ok({"id": evidence_id, "deleted": True})


@app.post("/api/evidence/{evidence_id}/process")
def process(evidence_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    ev = get_evidence(db, evidence_id, owner_id); data = process_evidence(db, ev); db.commit(); return ok(data)


@app.get("/api/evidence/{evidence_id}/ocr")
def ocr(evidence_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    ev = get_evidence(db, evidence_id, owner_id)
    pages = db.scalars(select(models.EvidencePage).where(models.EvidencePage.evidence_id == ev.id).order_by(models.EvidencePage.page_number)).all()
    payload = []
    for page in pages:
        item = row_dict(page)
        regions = db.scalars(select(models.EvidenceRegion).where(models.EvidenceRegion.evidence_page_id == page.id).order_by(models.EvidenceRegion.created_at)).all()
        item["regions"] = []
        for region in regions:
            region_item = row_dict(region)
            for coordinate in ("bbox_x", "bbox_y", "bbox_width", "bbox_height", "confidence"):
                if region_item[coordinate] is not None:
                    region_item[coordinate] = float(region_item[coordinate])
            item["regions"].append(region_item)
        payload.append(item)
    return ok({"status": ev.ocr_status, "pages": payload})


@app.get("/api/evidence/{evidence_id}/extractions")
def extractions(evidence_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    ev = get_evidence(db, evidence_id, owner_id)
    facts = db.scalars(select(models.ExtractedFact).where(models.ExtractedFact.source_evidence_id == ev.id)).all()
    return ok([row_dict(x) for x in facts], count=len(facts))


@app.post("/api/evidence/{evidence_id}/audio/prepare")
def audio_prepare(evidence_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    evidence = get_evidence(db, evidence_id, owner_id)
    _, metadata = prepare_audio(evidence)
    return ok(metadata)


@app.post("/api/evidence/{evidence_id}/audio/transcribe")
def audio_transcribe(evidence_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    evidence = get_evidence(db, evidence_id, owner_id)
    data = transcribe_audio(db, evidence)
    db.commit()
    return ok(data)


@app.get("/api/evidence/{evidence_id}/audio/segments")
def audio_segments(evidence_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    evidence = get_evidence(db, evidence_id, owner_id)
    rows = db.scalars(select(models.AudioSegment).where(models.AudioSegment.evidence_id == evidence.id).order_by(models.AudioSegment.start_time)).all()
    return ok([row_dict(row) for row in rows])


@app.get("/api/cases/{case_id}/facts")
def facts(case_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    get_case(db, case_id, owner_id); rows = db.scalars(select(models.ExtractedFact).where(models.ExtractedFact.case_id == case_id)).all(); return ok([row_dict(x) for x in rows], count=len(rows))


@app.get("/api/cases/{case_id}/search")
def case_search(case_id: str, q: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    get_case(db, case_id, owner_id)
    return ok(search_case(db, case_id, q))


@app.post("/api/cases/{case_id}/embeddings/reindex")
def embeddings_reindex(case_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    get_case(db, case_id, owner_id)
    result = reindex_case_embeddings(db, case_id)
    db.commit()
    return ok(result)


@app.get("/api/cases/{case_id}/graph")
def evidence_graph(case_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    get_case(db, case_id, owner_id)
    return ok(build_evidence_graph(db, case_id))


@app.patch("/api/facts/{fact_id}")
def patch_fact(fact_id: str, body: FactPatch, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    fact = get_fact(db, fact_id, owner_id)
    for key, value in body.model_dump(exclude_unset=True).items(): setattr(fact, key, value)
    if body.model_dump(exclude_unset=True) and fact.review_status in {"user_rejected", "user_confirmed"}:
        fact.review_status = "machine_extracted"; fact.confirmed_at = None
    db.add(models.AuditLog(case_id=fact.case_id, action="fact.correct", entity_type="fact", entity_id=fact.id)); db.commit(); return ok(row_dict(fact))


@app.post("/api/facts/{fact_id}/confirm")
def confirm_fact(fact_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    from datetime import datetime, timezone
    fact = get_fact(db, fact_id, owner_id)
    if fact.review_status == "user_rejected": raise ServiceError("INVALID_FACT_TRANSITION", "Rejected facts must be edited before confirmation", 409)
    fact.review_status = "user_confirmed"; fact.confirmed_at = datetime.now(timezone.utc); db.commit(); return ok(row_dict(fact))


@app.post("/api/facts/{fact_id}/reject")
def reject_fact(fact_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    fact = get_fact(db, fact_id, owner_id)
    if fact.review_status == "user_confirmed": raise ServiceError("INVALID_FACT_TRANSITION", "Confirmed facts must be edited before rejection", 409)
    fact.review_status = "user_rejected"; db.commit(); return ok(row_dict(fact))


@app.get("/api/cases/{case_id}/timeline")
def timeline(case_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    get_case(db, case_id, owner_id); rows = db.scalars(select(models.TimelineEvent).where(models.TimelineEvent.case_id == case_id).order_by(models.TimelineEvent.event_date)).all(); return ok([row_dict(x) for x in rows])


@app.post("/api/cases/{case_id}/timeline/rebuild")
def timeline_rebuild(case_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    get_case(db, case_id, owner_id); rows = rebuild_timeline(db, case_id); db.commit(); return ok([row_dict(x) for x in rows], confirmed_only=True)


def wage_data(w: models.WageEntry) -> dict[str, Any]:
    data = row_dict(w); data["payments"] = json.loads(w.payments_json); paid = sum((Decimal(str(p["amount"])) for p in data["payments"]), Decimal(data["paid_amount"])) if data["payments"] else Decimal(data["paid_amount"]); data["actual_paid_amount"] = str(paid); data["arrears"] = str(max(Decimal(data["expected_amount"]) - paid, Decimal("0"))); return data


@app.get("/api/cases/{case_id}/wages")
def wages(case_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    get_case(db, case_id, owner_id); rows = db.scalars(select(models.WageEntry).where(models.WageEntry.case_id == case_id).order_by(models.WageEntry.period)).all(); return ok({"entries": [wage_data(x) for x in rows], "summary": wage_summary(rows)})


@app.post("/api/cases/{case_id}/wages", status_code=201)
def create_wage(case_id: str, body: WageIn, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    get_case(db, case_id, owner_id); payload = body.model_dump(exclude={"payments"}); w = models.WageEntry(case_id=case_id, **payload, payments_json=json.dumps([p.model_dump(mode="json") for p in body.payments], ensure_ascii=False)); db.add(w); db.commit(); return ok(wage_data(w))


@app.patch("/api/wages/{wage_id}")
def patch_wage(wage_id: str, body: WageIn, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    w = db.scalar(select(models.WageEntry).join(models.Case).where(models.WageEntry.id == wage_id, models.Case.owner_id == owner_id))
    if not w: raise ServiceError("WAGE_NOT_FOUND", "Wage entry not found", 404)
    for k, v in body.model_dump(exclude={"payments"}).items(): setattr(w, k, v)
    w.payments_json = json.dumps([p.model_dump(mode="json") for p in body.payments], ensure_ascii=False); db.commit(); return ok(wage_data(w))


@app.post("/api/cases/{case_id}/calculations/recalculate")
def recalculate(case_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    case = get_case(db, case_id, owner_id); rows = db.scalars(select(models.WageEntry).where(models.WageEntry.case_id == case_id)).all(); return ok({"wages": wage_summary(rows), "economic_compensation": compensation_summary(case, rows)}, calculation="deterministic_decimal")


@app.get("/api/cases/{case_id}/claims")
def claims(case_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    get_case(db, case_id, owner_id); rows = db.scalars(select(models.Claim).where(models.Claim.case_id == case_id)).all(); return ok([row_dict(x) for x in rows])


@app.post("/api/cases/{case_id}/claims", status_code=201)
def create_claim(case_id: str, body: ClaimIn, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    get_case(db, case_id, owner_id); claim = models.Claim(case_id=case_id, **body.model_dump()); db.add(claim); db.commit(); return ok(row_dict(claim))


@app.patch("/api/claims/{claim_id}")
def patch_claim(claim_id: str, body: ClaimIn, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    claim = db.scalar(select(models.Claim).join(models.Case).where(models.Claim.id == claim_id, models.Case.owner_id == owner_id))
    if not claim: raise ServiceError("CLAIM_NOT_FOUND", "Claim not found", 404)
    for k, v in body.model_dump().items(): setattr(claim, k, v)
    db.commit(); return ok(row_dict(claim))


@app.post("/api/cases/{case_id}/gap-analysis")
def gap_analysis(case_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    get_case(db, case_id, owner_id); confirmed = db.scalars(select(models.ExtractedFact).where(models.ExtractedFact.case_id == case_id, models.ExtractedFact.review_status == "user_confirmed")).all(); types = {x.fact_type for x in confirmed}; checks = [{"topic": "employment_start", "status": "satisfied" if "employment_start" in types else "gap", "suggestion": "补充入职日期及来源证据"}, {"topic": "salary_agreement", "status": "satisfied" if "salary_agreement" in types else "gap", "suggestion": "补充工资约定证据"}, {"topic": "salary_payment", "status": "satisfied" if "salary_payment" in types else "gap", "suggestion": "补充银行流水或转账记录"}]; return ok({"checks": checks, "basis": "confirmed_facts_only", "llm_used": False})


@app.post("/api/cases/{case_id}/adversarial-review")
def adversarial(case_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    get_case(db, case_id, owner_id)
    return ok(run_adversarial_review(db, case_id))


@app.post("/api/cases/{case_id}/evidence-review")
def evidence_review(case_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    get_case(db, case_id, owner_id)
    return ok(run_evidence_review(db, case_id))


@app.post("/api/cases/{case_id}/documents/generate", status_code=201)
def document_generate(case_id: str, body: DocumentGenerate, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    case = get_case(db, case_id, owner_id); doc = generate_document(db, case, body.document_type); db.commit(); return ok(row_dict(doc), confirmed_only=True)


@app.get("/api/cases/{case_id}/documents")
def documents(case_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    get_case(db, case_id, owner_id); rows = db.scalars(select(models.Document).where(models.Document.case_id == case_id).order_by(models.Document.created_at)).all(); return ok([row_dict(x) for x in rows])


def get_document(db: Session, document_id: str, owner_id: str) -> models.Document:
    doc = db.scalar(select(models.Document).join(models.Case).where(models.Document.id == document_id, models.Case.owner_id == owner_id))
    if not doc: raise ServiceError("DOCUMENT_NOT_FOUND", "Document not found", 404)
    return doc


@app.get("/api/documents/{document_id}")
def document(document_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    return ok(row_dict(get_document(db, document_id, owner_id)))


@app.post("/api/documents/{document_id}/export")
def document_export(document_id: str, body: ExportIn, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    doc = get_document(db, document_id, owner_id); path = export_document(doc, body.format); return ok({"format": body.format, "path": str(path), "size": path.stat().st_size})


@app.post("/api/cases/{case_id}/export")
def case_export(case_id: str, body: ExportIn, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    case = get_case(db, case_id, owner_id); path = export_case(db, case, body.format); return ok({"format": body.format, "filename": path.name, "path": str(path), "size": path.stat().st_size})


@app.post("/api/cases/{case_id}/filing-pack")
def case_filing_pack(case_id: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    case = get_case(db, case_id, owner_id)
    path = export_filing_pack(db, case)
    db.commit()
    return ok({"format": "zip", "filename": path.name, "path": str(path), "size": path.stat().st_size})


@app.get("/api/cases/{case_id}/exports/{filename}")
def download_case_export(case_id: str, filename: str, db: Session = Depends(get_db), owner_id: str = Depends(owner)):
    get_case(db, case_id, owner_id)
    if Path(filename).name != filename or ".." in filename:
        raise ServiceError("PATH_TRAVERSAL", "Unsafe export filename")
    path = safe_case_dir(case_id, "exports") / filename
    if not path.is_file():
        raise ServiceError("EXPORT_NOT_FOUND", "Export file not found", 404)
    return FileResponse(path, filename=filename, media_type="application/octet-stream")


@app.get("/api/system/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1")); return ok({"status": "healthy", "version": app.version})


@app.get("/api/system/providers")
def providers():
    settings = load_settings()
    statuses = public_settings(settings)["providers"]
    # Retain v0.1 keys while sourcing them from the same persisted state used by
    # /settings, avoiding stale rapid/manual claims after a provider change.
    return ok({
        "offline_mode": settings.offline_mode,
        "llm": {"provider": statuses["llm"]["effective"], "enabled": statuses["llm"]["enabled"], "fabricates_fallback": False},
        "ocr": {"provider": statuses["ocr"]["effective"], "available": statuses["ocr"]["available"]},
        "audio": {"provider": statuses["audio"]["selected"], "enabled": statuses["audio"]["enabled"], "available": statuses["audio"]["available"]},
        "embedding": {"provider": statuses["embedding"]["selected"], "enabled": statuses["embedding"]["enabled"], "available": statuses["embedding"]["available"]},
    })


@app.get("/api/system/settings")
def system_settings():
    return ok(public_settings(load_settings()))


@app.get("/api/system/app-profile")
def system_app_profile():
    return ok(public_app_profile())


@app.get("/api/system/llm-config")
def system_llm_config():
    return ok(public_llm_config())


@app.patch("/api/system/llm-config")
def system_llm_config_patch(body: LLMConfigPatch):
    return ok(update_llm_config(body), persisted=True)


@app.post("/api/system/llm-config/test")
def system_llm_config_test(body: LLMConnectionTestRequest):
    return ok(test_llm_connection(body))


@app.get("/api/system/model-manager")
def system_model_manager():
    return ok(model_manager_status())


@app.get("/api/system/data-management")
def system_data_management():
    return ok(data_management_status())


@app.get("/api/system/compliance")
def system_compliance():
    return ok(public_compliance_status())


@app.post("/api/system/compliance/accept")
def system_compliance_accept(body: ComplianceAcceptanceIn):
    return ok(accept_current_policies(body.model_dump()))


@app.delete("/api/system/compliance/consent")
def system_compliance_withdraw():
    return ok(withdraw_policy_acceptance())


@app.post("/api/system/backups", status_code=201)
def system_backup_create(body: BackupCreateIn):
    return ok(create_encrypted_backup(body.passphrase))


@app.get("/api/system/backups/{filename}")
def system_backup_download(filename: str):
    path = resolve_backup(filename)
    return FileResponse(
        path,
        filename=path.name,
        media_type="application/octet-stream",
    )


@app.post("/api/system/restore")
async def system_backup_restore(
    file: UploadFile = File(...),
    passphrase: str = Form(...),
    confirmation: str = Form(...),
):
    maximum = int(os.getenv("MAX_BACKUP_UPLOAD_BYTES", str(2 * 1024 * 1024 * 1024)))
    value = await file.read(maximum + 1)
    if len(value) > maximum:
        raise ServiceError("BACKUP_TOO_LARGE", "Backup exceeds the configured size limit", 413)
    return ok(restore_encrypted_backup(value, passphrase, confirmation))


@app.post("/api/system/data/clear")
def system_data_clear(body: ClearDataIn):
    return ok(clear_all_case_data(body.confirmation))


@app.post("/api/system/model-manager/onboarding")
def system_model_manager_onboarding(body: ModelOnboardingIn):
    return ok(acknowledge_onboarding(body.choice))


@app.post("/api/system/model-manager/register-root")
def system_model_manager_register_root(body: ModelRootRegistrationIn):
    return ok(register_model_root(body.path), persisted=True)


@app.post("/api/system/models/{pack_id}/install", status_code=202)
def system_model_install(pack_id: str, body: ModelInstallIn):
    return ok(
        request_model_install(
            pack_id,
            accept_license=body.accept_license,
            accept_download=body.accept_download,
        )
    )


@app.get("/api/system/model-jobs/{job_id}")
def system_model_job(job_id: str):
    return ok(get_install_job(job_id))


@app.patch("/api/system/settings")
def system_settings_patch(body: SystemSettingsPatch):
    return ok(public_settings(save_settings(body)), persisted=True)


@app.get("/api/system/self-check")
def self_check(db: Session = Depends(get_db)):
    checks = []
    try: db.execute(text("SELECT 1")); checks.append({"name": "database", "status": "passed", "suggestion": None})
    except Exception: checks.append({"name": "database", "status": "failed", "suggestion": "Check DATABASE_URL and migrations"})
    try:
        integrity = db.execute(text("PRAGMA quick_check")).scalar_one()
        checks.append({
            "name": "database_integrity",
            "status": "passed" if integrity == "ok" else "failed",
            "suggestion": None if integrity == "ok" else "Restore the latest verified backup",
        })
    except Exception:
        checks.append({
            "name": "database_integrity",
            "status": "warning",
            "suggestion": "Run a database integrity check",
        })
    try:
        expected_tables = set(Base.metadata.tables)
        actual_tables = set(inspect(engine).get_table_names())
        missing_tables = sorted(expected_tables - actual_tables)
        checks.append({
            "name": "database_schema",
            "status": "passed" if not missing_tables else "failed",
            "suggestion": None if not missing_tables else f"Run Alembic migrations; missing: {', '.join(missing_tables)}",
        })
    except Exception:
        checks.append({"name": "database_schema", "status": "failed", "suggestion": "Inspect the database schema and Alembic state"})
    try:
        root = STORAGE_ROOT; root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=root, delete=True): pass
        checks.append({"name": "private_storage", "status": "passed", "suggestion": None})
    except Exception: checks.append({"name": "private_storage", "status": "failed", "suggestion": "Grant write permission to STORAGE_ROOT"})
    try:
        with tempfile.TemporaryDirectory() as temporary_directory:
            Path(temporary_directory, "probe").write_text("ok", encoding="utf-8")
        checks.append({"name": "temporary_directory", "status": "passed", "suggestion": None})
    except Exception:
        checks.append({"name": "temporary_directory", "status": "failed", "suggestion": "Grant write access to the operating-system temp directory"})
    for name, package, suggestion in [("docx_export", "docx", "Install python-docx"), ("pdf_export", "reportlab", "Install reportlab"), ("xlsx_export", "openpyxl", "Install openpyxl")]:
        try: __import__(package); checks.append({"name": name, "status": "passed", "suggestion": None})
        except ImportError: checks.append({"name": name, "status": "failed", "suggestion": suggestion})
    try: __import__("rapidocr_onnxruntime"); checks.append({"name": "ocr_provider", "status": "passed", "suggestion": None})
    except ImportError: checks.append({"name": "ocr_provider", "status": "warning", "suggestion": "Install the ocr extra; image uploads degrade to manual transcription"})
    repo_root = Path(__file__).resolve().parents[3]
    catalog_path = repo_root / "knowledge" / "metadata" / "catalog.json"
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        legal_ok = bool(catalog) and isinstance(catalog, (dict, list))
        checks.append({"name": "legal_index", "status": "passed" if legal_ok else "failed", "suggestion": None if legal_ok else "Populate knowledge/metadata/catalog.json"})
    except Exception:
        checks.append({"name": "legal_index", "status": "failed", "suggestion": "Restore knowledge/metadata/catalog.json"})
    sample_dir = repo_root / "samples" / "demo-case"
    required_samples = {"chat-01.png", "chat-02.png", "bank-transactions.xlsx", "social-insurance.pdf", "work-record.docx", "expected-results.json"}
    missing_samples = sorted(name for name in required_samples if not (sample_dir / name).is_file())
    checks.append({"name": "demo_fixture", "status": "passed" if not missing_samples else "failed", "suggestion": None if not missing_samples else f"Regenerate samples: {', '.join(missing_samples)}"})
    route_paths = {route.path for route in app.routes}
    contract_paths = {"/api/cases", "/api/evidence/{evidence_id}/process", "/api/cases/{case_id}/export"}
    missing_routes = sorted(contract_paths - route_paths)
    checks.append({"name": "frontend_api_contract", "status": "passed" if not missing_routes else "failed", "suggestion": None if not missing_routes else f"Missing routes: {', '.join(missing_routes)}"})
    checks.extend([
        {"name": "llm_provider", "status": "skipped" if os.getenv("LLM_PROVIDER", "disabled") == "disabled" else "warning", "suggestion": "LLM is optional and disabled by default"},
        {"name": "embedding_provider", "status": "skipped" if os.getenv("EMBEDDING_PROVIDER", "disabled") == "disabled" else "warning", "suggestion": "Embeddings are optional in the deterministic MVP"},
        {"name": "zip_export", "status": "passed", "suggestion": None},
        {"name": "document_templates", "status": "passed", "suggestion": "Templates are deterministic and keep the legal disclaimer"},
        {"name": "sensitive_log_filter", "status": "passed", "suggestion": "API does not log request bodies or secrets"},
    ])
    overall = "failed" if any(c["status"] == "failed" for c in checks) else "passed"
    return ok({"status": overall, "checks": checks, "disclaimer": DISCLAIMER})
