from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


@dataclass(slots=True)
class AudioSegmentResult:
    speaker_id: str
    start_time: Decimal
    end_time: Decimal
    text: str
    confidence: Decimal | None = None


@dataclass(slots=True)
class AudioTranscriptionResult:
    provider: str
    device: str
    segments: list[AudioSegmentResult]
    raw_text: str


class MOSSAudioProvider:
    name = "moss-transcribe-diarize"

    def availability(self) -> tuple[bool, str]:
        python_path = Path(os.getenv("MOSS_PYTHON", ""))
        model_path = Path(os.getenv("MOSS_MODEL_PATH", ""))
        if not python_path.is_file():
            return False, "runtime_not_installed"
        if not model_path.is_dir():
            return False, "model_not_installed"
        return True, "available"

    def transcribe(self, audio_path: Path, device: str = "auto") -> AudioTranscriptionResult:
        python_path = Path(os.environ["MOSS_PYTHON"])
        model_path = Path(os.environ["MOSS_MODEL_PATH"])
        worker = Path(__file__).resolve().parents[1] / "model_workers" / "moss_transcribe.py"
        completed = subprocess.run(
            [str(python_path), str(worker), "--model", str(model_path), "--audio", str(audio_path), "--device", device],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=int(os.getenv("MOSS_TRANSCRIBE_TIMEOUT", "1800")),
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if completed.returncode != 0:
            error = completed.stderr.strip().splitlines()[-1:] or ["unknown worker failure"]
            raise RuntimeError(error[0])
        payload = json.loads(completed.stdout)
        return AudioTranscriptionResult(
            provider=self.name,
            device=payload["device"],
            raw_text=payload["raw_text"],
            segments=[
                AudioSegmentResult(
                    speaker_id=item["speaker_id"],
                    start_time=Decimal(str(item["start_time"])),
                    end_time=Decimal(str(item["end_time"])),
                    text=item["text"],
                    confidence=Decimal(str(item["confidence"])) if item.get("confidence") is not None else None,
                )
                for item in payload["segments"]
            ],
        )


class AudioRouter:
    def __init__(self):
        self.provider = MOSSAudioProvider()

    def availability(self) -> tuple[bool, str]:
        selected = os.getenv("AUDIO_PROVIDER", "disabled").strip().lower()
        if selected == "disabled":
            return False, "disabled"
        if selected != self.provider.name:
            return False, "unknown_provider"
        return self.provider.availability()

    def transcribe(self, audio_path: Path, device: str = "auto") -> AudioTranscriptionResult:
        available, reason = self.availability()
        if not available:
            raise RuntimeError(reason)
        return self.provider.transcribe(audio_path, device=device)
