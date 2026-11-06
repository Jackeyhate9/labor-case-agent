from __future__ import annotations

import importlib.util
import os
import sys
import threading
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from .app_paths import app_data_root
from .services import ServiceError


OCRProviderName = Literal[
    "auto",
    "rapidocr",
    "paddleocr",
    "windows-ocr",
    "unlimited-ocr",
    "ollama-ocr",
    "disabled",
]
AudioProviderName = Literal["moss-transcribe-diarize", "disabled"]
EmbeddingProviderName = Literal["bge-m3", "nemotron-3-embed-1b", "disabled"]
LLMProviderName = Literal["ollama", "openai-compatible", "deepseek-compatible", "qwen-compatible", "disabled"]


class SystemSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    offline_mode: bool = True
    ocr_provider: OCRProviderName = "auto"
    audio_provider: AudioProviderName = "disabled"
    embedding_provider: EmbeddingProviderName = "disabled"
    llm_provider: LLMProviderName = "disabled"


class SystemSettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    offline_mode: bool | None = None
    ocr_provider: OCRProviderName | None = None
    audio_provider: AudioProviderName | None = None
    embedding_provider: EmbeddingProviderName | None = None
    llm_provider: LLMProviderName | None = None


_LOCK = threading.RLock()


def settings_path() -> Path:
    path = Path(os.getenv("SYSTEM_SETTINGS_FILE", app_data_root() / "system-settings.json")).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_settings() -> SystemSettings:
    path = settings_path()
    with _LOCK:
        if not path.exists():
            return SystemSettings()
        try:
            return SystemSettings.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError, ValueError) as exc:
            raise ServiceError("SETTINGS_CORRUPTED", "Persisted system settings are invalid", 500) from exc


def save_settings(patch: SystemSettingsPatch) -> SystemSettings:
    if (
        os.getenv("APP_EDITION", "distribution").strip().lower() == "roadshow"
        and patch.model_dump(exclude_none=True)
    ):
        raise ServiceError(
            "APP_PROFILE_LOCKED",
            "Provider settings are managed by the roadshow environment",
            409,
        )
    with _LOCK:
        current = load_settings()
        values = current.model_dump()
        values.update(patch.model_dump(exclude_none=True))
        updated = SystemSettings.model_validate(values)
        path = settings_path()
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(updated.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)
        # Keep existing local providers aligned for this process. Secrets are
        # never accepted or written; deployment-level credentials remain env-only.
        os.environ["OCR_PROVIDER"] = updated.ocr_provider
        os.environ["AUDIO_PROVIDER"] = updated.audio_provider
        os.environ["EMBEDDING_PROVIDER"] = updated.embedding_provider
        os.environ["LLM_PROVIDER"] = updated.llm_provider
        return updated


def _package_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _ocr_status(selected: str) -> dict[str, Any]:
    ollama_ocr_model = os.getenv("OLLAMA_OCR_MODEL", "").strip()
    if not ollama_ocr_model and os.getenv("APP_EDITION", "distribution").strip().lower() == "roadshow":
        ollama_ocr_model = "unlimitedocrlocal:latest"
    availability = {
        "rapidocr": _package_available("rapidocr_onnxruntime"),
        "paddleocr": _package_available("paddleocr"),
        "windows-ocr": os.name == "nt" and _package_available("winrt"),
        "unlimited-ocr": bool(os.getenv("UNLIMITED_OCR_MODEL_PATH"))
        and (
            Path(os.getenv("UNLIMITED_OCR_PYTHON", "")).is_file()
            or (_package_available("torch") and _package_available("transformers"))
        ),
        "ollama-ocr": bool(ollama_ocr_model),
    }
    effective = next(
        (
            name
            for name in (
                "unlimited-ocr",
                "ollama-ocr",
                "paddleocr",
                "windows-ocr",
                "rapidocr",
            )
            if availability[name]
        ),
        None,
    ) if selected == "auto" else selected
    enabled = selected != "disabled"
    available = bool(enabled and effective and availability.get(effective, False))
    return {"selected": selected, "effective": effective if enabled else "disabled", "enabled": enabled, "available": available, "status": "available" if available else "disabled" if not enabled else "unavailable", "candidates": availability}


def _audio_status(selected: str) -> dict[str, Any]:
    runtime = Path(os.getenv("MOSS_PYTHON", ""))
    model = Path(os.getenv("MOSS_MODEL_PATH", ""))
    available = selected != "disabled" and runtime.is_file() and model.is_dir()
    reason = "available" if available else "disabled" if selected == "disabled" else "runtime_not_installed" if not runtime.is_file() else "model_not_installed"
    return {"selected": selected, "effective": selected, "enabled": selected != "disabled", "available": available, "status": reason}


def _embedding_status(selected: str) -> dict[str, Any]:
    if selected == "disabled":
        return {"selected": selected, "effective": selected, "enabled": False, "available": False, "status": "disabled"}
    model_var = "BGE_M3_MODEL_PATH" if selected == "bge-m3" else "NEMOTRON_EMBED_MODEL_PATH"
    runtime = Path(os.getenv("EMBEDDING_PYTHON", sys.executable))
    model = Path(os.getenv(model_var, ""))
    weights = model.is_dir() and any((model / name).is_file() for name in ("model.safetensors", "pytorch_model.bin"))
    available = runtime.is_file() and weights
    reason = "available" if available else "runtime_not_installed" if not runtime.is_file() else "model_not_installed" if not model.is_dir() else "model_weights_incomplete"
    return {"selected": selected, "effective": selected, "enabled": True, "available": available, "status": reason}


def _llm_status(selected: str, offline_mode: bool) -> dict[str, Any]:
    cloud = selected in {"openai-compatible", "deepseek-compatible", "qwen-compatible"}
    effective = "disabled" if selected == "disabled" or (offline_mode and cloud) else selected
    base_url = bool(os.getenv("LLM_BASE_URL"))
    key_configured = bool(os.getenv("LLM_API_KEY"))
    configured = effective == "ollama" and base_url or effective not in {"disabled", "ollama"} and base_url and key_configured
    status = "blocked_by_offline_mode" if offline_mode and cloud else "disabled" if effective == "disabled" else "configured" if configured else "not_configured"
    return {"selected": selected, "effective": effective, "enabled": effective != "disabled", "available": configured, "status": status, "api_key_configured": key_configured}


def effective_settings(settings: SystemSettings) -> SystemSettings:
    edition = os.getenv("APP_EDITION", "distribution").strip().lower()
    if edition == "roadshow":
        values = settings.model_dump()
        values.update(
            {
                "ocr_provider": os.getenv("OCR_PROVIDER", values["ocr_provider"]),
                "audio_provider": os.getenv("AUDIO_PROVIDER", values["audio_provider"]),
                "embedding_provider": os.getenv(
                    "EMBEDDING_PROVIDER", values["embedding_provider"]
                ),
                "llm_provider": os.getenv("LLM_PROVIDER", values["llm_provider"]),
            }
        )
        try:
            settings = SystemSettings.model_validate(values)
        except ValidationError as exc:
            raise ServiceError(
                "APP_PROFILE_INVALID",
                "Roadshow provider environment contains an unsupported value",
                500,
            ) from exc
    return settings


def public_settings(settings: SystemSettings) -> dict[str, Any]:
    edition = os.getenv("APP_EDITION", "distribution").strip().lower()
    settings = effective_settings(settings)
    return {
        **settings.model_dump(),
        "providers": {
            "ocr": _ocr_status(settings.ocr_provider),
            "audio": _audio_status(settings.audio_provider),
            "embedding": _embedding_status(settings.embedding_provider),
            "llm": _llm_status(settings.llm_provider, settings.offline_mode),
        },
        "secrets": {"storage": "environment_only", "returned": False},
        "profile": {
            "edition": edition,
            "locked": edition == "roadshow",
            "source": "environment" if edition == "roadshow" else "user",
        },
    }
