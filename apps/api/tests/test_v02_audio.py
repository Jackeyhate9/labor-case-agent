import hashlib
import io
import math
import struct
import wave
from pathlib import Path


def envelope(response, status=200):
    assert response.status_code == status, response.text
    payload = response.json()
    assert payload["success"] is True
    return payload["data"]


def tone_wav(duration=0.25, sample_rate=16_000):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        frames = [
            struct.pack("<h", int(2000 * math.sin(2 * math.pi * 440 * index / sample_rate)))
            for index in range(int(duration * sample_rate))
        ]
        audio.writeframes(b"".join(frames))
    return stream.getvalue()


def upload_audio(client, case_id, monkeypatch):
    from app import services

    monkeypatch.setattr(services, "MAX_UPLOAD_BYTES", 2 * 1024 * 1024)
    content = tone_wav()
    response = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("call.wav", content, "audio/wav")},
    )
    return content, envelope(response, 201)


def test_audio_original_supports_inline_preview_and_byte_ranges(client, case_id, monkeypatch):
    content, evidence = upload_audio(client, case_id, monkeypatch)
    preview = envelope(client.get(f"/api/evidence/{evidence['id']}/preview"))
    assert preview["kind"] == "audio"

    partial = client.get(
        preview["content_url"],
        headers={"Range": "bytes=0-15"},
    )
    assert partial.status_code == 206
    assert partial.headers["content-range"] == f"bytes 0-15/{len(content)}"
    assert partial.content == content[:16]


def test_audio_prepare_creates_separate_pcm_derivative(client, case_id, monkeypatch):
    content, evidence = upload_audio(client, case_id, monkeypatch)
    original_hash = hashlib.sha256(content).hexdigest()
    prepared = envelope(client.post(f"/api/evidence/{evidence['id']}/audio/prepare"))
    assert prepared["sample_rate"] == 16000
    assert prepared["channels"] == 1
    assert prepared["duration_seconds"] > 0
    assert prepared["derived_sha256"] != original_hash

    original = client.get(f"/api/evidence/{evidence['id']}/content")
    assert hashlib.sha256(original.content).hexdigest() == original_hash


def test_audio_transcription_fails_explicitly_when_moss_is_not_installed(
    client, case_id, monkeypatch
):
    _, evidence = upload_audio(client, case_id, monkeypatch)
    monkeypatch.setenv("MOSS_MODEL_PATH", "Z:/definitely-missing-moss-model")
    monkeypatch.setenv("MOSS_PYTHON", "Z:/missing-python.exe")
    response = client.post(f"/api/evidence/{evidence['id']}/audio/transcribe")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AUDIO_PROVIDER_UNAVAILABLE"
    segments = envelope(client.get(f"/api/evidence/{evidence['id']}/audio/segments"))
    assert segments == []


def test_real_moss_transcription_creates_timestamped_segments_and_candidate_facts(
    client, case_id, monkeypatch
):
    root = Path(__file__).resolve().parents[3]
    runtime = root / ".venv-moss" / "Scripts" / "python.exe"
    model = root / "models" / "MOSS-Transcribe-Diarize"
    sample = root / "samples" / "demo-case" / "wage-call.wav"
    if not runtime.is_file() or not (model / "config.json").is_file() or not sample.is_file():
        import pytest

        pytest.skip("local MOSS runtime, model, or audio fixture is unavailable")
    from app import services

    monkeypatch.setattr(services, "MAX_UPLOAD_BYTES", 4 * 1024 * 1024)
    monkeypatch.setenv("MOSS_PYTHON", str(runtime))
    monkeypatch.setenv("MOSS_MODEL_PATH", str(model))
    monkeypatch.setenv("AUDIO_PROVIDER", "moss-transcribe-diarize")
    evidence = envelope(
        client.post(
            f"/api/cases/{case_id}/evidence",
            files={"file": ("wage-call.wav", sample.read_bytes(), "audio/wav")},
        ),
        201,
    )

    result = envelope(client.post(f"/api/evidence/{evidence['id']}/audio/transcribe"))
    assert result["provider"] == "moss-transcribe-diarize"
    assert result["device"] == "cuda"
    assert result["segments"]
    assert all(float(segment["end_time"]) > float(segment["start_time"]) >= 0 for segment in result["segments"])
    assert any("工资" in segment["text"] for segment in result["segments"])
    assert result["candidate_facts"]
    assert any(fact["source_audio_segment_id"] for fact in result["candidate_facts"])
