from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from . import models
from .providers.audio import AudioRouter
from .services import ServiceError, extract_candidate_facts, row_dict, safe_case_dir


def _run(command: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def prepare_audio(evidence: models.Evidence) -> tuple[Path, dict[str, object]]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise ServiceError("FFMPEG_UNAVAILABLE", "FFmpeg and ffprobe are required for audio evidence", 503)
    source = safe_case_dir(evidence.case_id, "original") / evidence.stored_filename
    if not source.is_file():
        raise ServiceError("FILE_MISSING", "Stored evidence file is missing", 404)
    target = safe_case_dir(evidence.case_id, "derived") / f"audio-{evidence.id}-16k.wav"
    converted = _run([ffmpeg, "-nostdin", "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(target)])
    if converted.returncode != 0 or not target.is_file():
        raise ServiceError("AUDIO_CONVERSION_FAILED", "FFmpeg could not decode this audio/video file", 422)
    probed = _run([ffprobe, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=sample_rate,channels:format=duration", "-of", "json", str(target)])
    if probed.returncode != 0:
        raise ServiceError("AUDIO_PROBE_FAILED", "ffprobe could not inspect the derived audio", 422)
    info = json.loads(probed.stdout)
    stream = info["streams"][0]
    metadata = {
        "sample_rate": int(stream["sample_rate"]),
        "channels": int(stream["channels"]),
        "duration_seconds": float(info["format"]["duration"]),
        "derived_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "derived_filename": target.name,
    }
    return target, metadata


def transcribe_audio(db: Session, evidence: models.Evidence, device: str = "auto") -> dict[str, object]:
    router = AudioRouter()
    available, reason = router.availability()
    if not available:
        raise ServiceError("AUDIO_PROVIDER_UNAVAILABLE", f"MOSS Transcribe Diarize unavailable: {reason}", 503)
    audio_path, preparation = prepare_audio(evidence)
    try:
        result = router.transcribe(audio_path, device=device)
    except Exception as exc:
        raise ServiceError("AUDIO_TRANSCRIPTION_FAILED", f"MOSS transcription failed: {type(exc).__name__}", 422) from exc
    db.query(models.AudioSegment).filter(models.AudioSegment.evidence_id == evidence.id).delete()
    rows = []
    for segment in result.segments:
        row = models.AudioSegment(
            evidence_id=evidence.id,
            speaker_id=segment.speaker_id,
            start_time=segment.start_time,
            end_time=segment.end_time,
            text=segment.text,
            confidence=segment.confidence,
        )
        db.add(row)
        rows.append(row)
    db.flush()
    db.query(models.ExtractedFact).filter(models.ExtractedFact.source_evidence_id == evidence.id).delete()
    db.query(models.EvidencePage).filter(models.EvidencePage.evidence_id == evidence.id).delete()
    transcript_page = models.EvidencePage(
        evidence_id=evidence.id,
        page_number=1,
        ocr_text="\n".join(segment.text for segment in result.segments),
        ocr_engine=result.provider,
    )
    db.add(transcript_page)
    db.flush()
    facts = extract_candidate_facts(db, evidence, [transcript_page])
    segment_by_text = {row.text.strip(): row for row in rows}
    for fact in facts:
        segment = segment_by_text.get((fact.source_quote or "").strip())
        if segment:
            fact.source_audio_segment_id = segment.id
    evidence.processing_status = "completed"
    evidence.ocr_status = "not_required"
    db.add(models.AuditLog(case_id=evidence.case_id, action="evidence.audio.transcribe", entity_type="evidence", entity_id=evidence.id, details=json.dumps({"provider": result.provider, "device": result.device, "segments": len(rows)})))
    return {"provider": result.provider, "device": result.device, "preparation": preparation, "segments": [row_dict(row) for row in rows], "raw_text": result.raw_text, "candidate_facts": [row_dict(fact) for fact in facts]}
