from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def uid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(200))
    case_type: Mapped[str] = mapped_column(String(80), default="wage_arrears")
    status: Mapped[str] = mapped_column(String(40), default="draft")
    jurisdiction_region: Mapped[str | None] = mapped_column(String(120))
    employment_start_date: Mapped[date | None] = mapped_column(Date)
    employment_end_date: Mapped[date | None] = mapped_column(Date)
    owner_id: Mapped[str] = mapped_column(String(100), default="local-user")
    risk_flags: Mapped[str] = mapped_column(Text, default="[]")
    summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    parties = relationship("Party", cascade="all, delete-orphan")
    evidence = relationship("Evidence", cascade="all, delete-orphan")
    facts = relationship("ExtractedFact", cascade="all, delete-orphan")
    timeline = relationship("TimelineEvent", cascade="all, delete-orphan")
    wages = relationship("WageEntry", cascade="all, delete-orphan")
    claims = relationship("Claim", cascade="all, delete-orphan")
    documents = relationship("Document", cascade="all, delete-orphan")
    audits = relationship("AuditLog", cascade="all, delete-orphan")


class Party(Base):
    __tablename__ = "parties"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    party_type: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    alias: Mapped[str | None] = mapped_column(String(200))
    identity_type: Mapped[str | None] = mapped_column(String(40))
    identity_number_masked: Mapped[str | None] = mapped_column(String(100))
    company_name: Mapped[str | None] = mapped_column(String(200))
    unified_social_credit_code: Mapped[str | None] = mapped_column(String(30))
    role_description: Mapped[str | None] = mapped_column(Text)
    contact_info_encrypted: Mapped[str | None] = mapped_column(Text)


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    evidence_number: Mapped[str] = mapped_column(String(30))
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(120))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    file_size: Mapped[int] = mapped_column(Integer)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    document_type: Mapped[str] = mapped_column(String(60), default="other")
    source_type: Mapped[str] = mapped_column(String(60), default="upload")
    source_description: Mapped[str | None] = mapped_column(Text)
    upload_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    processing_status: Mapped[str] = mapped_column(String(30), default="pending")
    ocr_status: Mapped[str] = mapped_column(String(30), default="pending")
    review_status: Mapped[str] = mapped_column(String(30), default="unreviewed")
    date_start: Mapped[date | None] = mapped_column(Date)
    date_end: Mapped[date | None] = mapped_column(Date)
    confidentiality_level: Mapped[str] = mapped_column(String(30), default="private")
    pages = relationship("EvidencePage", cascade="all, delete-orphan")
    audio_segments = relationship("AudioSegment", cascade="all, delete-orphan")


class EvidencePage(Base):
    __tablename__ = "evidence_pages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    image_path: Mapped[str | None] = mapped_column(Text)
    ocr_text: Mapped[str] = mapped_column(Text, default="")
    ocr_engine: Mapped[str] = mapped_column(String(40), default="parser")
    ocr_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    rotation: Mapped[int] = mapped_column(Integer, default=0)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    regions = relationship("EvidenceRegion", cascade="all, delete-orphan")


class EvidenceRegion(Base):
    __tablename__ = "evidence_regions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    evidence_page_id: Mapped[str] = mapped_column(ForeignKey("evidence_pages.id", ondelete="CASCADE"), index=True)
    region_type: Mapped[str] = mapped_column(String(40), default="text")
    bounding_box: Mapped[str] = mapped_column(Text, default="[]")
    bbox_x: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    bbox_y: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    bbox_width: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    bbox_height: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    raw_text: Mapped[str] = mapped_column(Text, default="")
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AudioSegment(Base):
    __tablename__ = "audio_segments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), index=True)
    speaker_id: Mapped[str] = mapped_column(String(30))
    start_time: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    end_time: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))


class EvidenceEmbedding(Base):
    __tablename__ = "evidence_embeddings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    entity_type: Mapped[str] = mapped_column(String(30), index=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    embedding_model_version: Mapped[str] = mapped_column(String(80), index=True)
    dimensions: Mapped[int] = mapped_column(Integer)
    vector_json: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ExtractedFact(Base):
    __tablename__ = "facts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    fact_type: Mapped[str] = mapped_column(String(50), default="other")
    subject_party_id: Mapped[str | None] = mapped_column(ForeignKey("parties.id", ondelete="SET NULL"))
    predicate: Mapped[str] = mapped_column(String(100), default="states")
    object_value: Mapped[str] = mapped_column(Text)
    normalized_value: Mapped[str | None] = mapped_column(Text)
    date_value: Mapped[date | None] = mapped_column(Date)
    date_precision: Mapped[str | None] = mapped_column(String(30))
    amount_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    source_evidence_id: Mapped[str | None] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"))
    source_page: Mapped[int | None] = mapped_column(Integer)
    source_region_id: Mapped[str | None] = mapped_column(ForeignKey("evidence_regions.id", ondelete="SET NULL"))
    source_audio_segment_id: Mapped[str | None] = mapped_column(ForeignKey("audio_segments.id", ondelete="SET NULL"))
    source_quote: Mapped[str | None] = mapped_column(Text)
    extraction_method: Mapped[str] = mapped_column(String(40), default="rule")
    machine_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    review_status: Mapped[str] = mapped_column(String(30), default="machine_extracted")
    user_corrected_value: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    conflict_group_id: Mapped[str | None] = mapped_column(String(36))
    notes: Mapped[str | None] = mapped_column(Text)


class TimelineEvent(Base):
    __tablename__ = "timeline_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    event_date: Mapped[date | None] = mapped_column(Date)
    date_precision: Mapped[str | None] = mapped_column(String(30))
    event_type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    source_fact_id: Mapped[str] = mapped_column(ForeignKey("facts.id", ondelete="CASCADE"))
    source_evidence_id: Mapped[str | None] = mapped_column(ForeignKey("evidence.id", ondelete="SET NULL"))


class WageEntry(Base):
    __tablename__ = "wages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    period: Mapped[str] = mapped_column(String(20))
    expected_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    payments_json: Mapped[str] = mapped_column(Text, default="[]")
    payer: Mapped[str | None] = mapped_column(String(200))
    payer_relationship: Mapped[str | None] = mapped_column(String(80))
    payment_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)


class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    claim_type: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(200))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(String(30), default="draft")
    basis: Mapped[str | None] = mapped_column(Text)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    document_type: Mapped[str] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(200))
    content_markdown: Mapped[str] = mapped_column(Text)
    sources_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str | None] = mapped_column(String(36))
    details: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
