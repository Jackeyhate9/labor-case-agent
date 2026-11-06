from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .app_paths import public_storage_contract
from .model_manager import model_root_info
from .services import ServiceError


def app_edition() -> str:
    edition = os.getenv("APP_EDITION", "distribution").strip().lower()
    if edition not in {"distribution", "roadshow"}:
        raise ServiceError(
            "APP_EDITION_INVALID",
            "APP_EDITION must be either distribution or roadshow",
            500,
        )
    return edition


def _path_status(path_value: str, runtime_value: str = "") -> dict[str, Any]:
    model_path = Path(path_value).resolve() if path_value else None
    runtime_path = Path(runtime_value).resolve() if runtime_value else None
    model_present = bool(model_path and model_path.is_dir())
    runtime_present = bool(runtime_path and runtime_path.is_file()) if runtime_value else True
    return {
        "configured": model_present and runtime_present,
        "model_path": str(model_path) if model_path else "",
        "runtime_path": str(runtime_path) if runtime_path else "",
        "model_present": model_present,
        "runtime_present": runtime_present,
    }


def activate_app_profile() -> None:
    if app_edition() != "roadshow":
        return
    ollama_base_url = os.getenv("LLM_BASE_URL", "").strip() or os.getenv(
        "OLLAMA_BASE_URL", ""
    ).strip()
    ollama_model = os.getenv("LLM_MODEL", "").strip() or os.getenv("OLLAMA_MODEL", "").strip()
    if ollama_base_url:
        os.environ["LLM_BASE_URL"] = ollama_base_url.rstrip("/")
    if ollama_model:
        os.environ["LLM_MODEL"] = ollama_model
    if ollama_base_url and ollama_model:
        os.environ["LLM_PROVIDER"] = "ollama"

    unlimited = _path_status(
        os.getenv("UNLIMITED_OCR_MODEL_PATH", ""),
        os.getenv("UNLIMITED_OCR_PYTHON", ""),
    )
    ollama_ocr_base_url = (
        os.getenv("OLLAMA_OCR_BASE_URL", "").strip()
        or os.getenv("OLLAMA_BASE_URL", "").strip()
        or ollama_base_url
    )
    if unlimited["configured"]:
        os.environ["OCR_PROVIDER"] = "unlimited-ocr"
    elif ollama_ocr_base_url:
        os.environ.setdefault("OLLAMA_OCR_MODEL", "unlimitedocrlocal:latest")
        os.environ["OCR_PROVIDER"] = "ollama-ocr"

    moss = _path_status(
        os.getenv("MOSS_MODEL_PATH", ""),
        os.getenv("MOSS_PYTHON", ""),
    )
    if moss["configured"]:
        os.environ["AUDIO_PROVIDER"] = "moss-transcribe-diarize"

    embedding_runtime = os.getenv("EMBEDDING_PYTHON", "")
    bge = _path_status(os.getenv("BGE_M3_MODEL_PATH", ""), embedding_runtime)
    nemotron = _path_status(os.getenv("NEMOTRON_EMBED_MODEL_PATH", ""), embedding_runtime)
    preferred = os.getenv("ROADSHOW_EMBEDDING_PROVIDER", "").strip().lower()
    if preferred in {"nemotron", "nemotron-3-embed-1b"} and nemotron["configured"]:
        os.environ["EMBEDDING_PROVIDER"] = "nemotron-3-embed-1b"
    elif bge["configured"]:
        os.environ["EMBEDDING_PROVIDER"] = "bge-m3"
    elif nemotron["configured"]:
        os.environ["EMBEDDING_PROVIDER"] = "nemotron-3-embed-1b"


def public_app_profile() -> dict[str, Any]:
    edition = app_edition()
    activate_app_profile()
    ollama_base_url = os.getenv("LLM_BASE_URL", "").strip() or os.getenv(
        "OLLAMA_BASE_URL", ""
    ).strip()
    ollama_model = os.getenv("LLM_MODEL", "").strip() or os.getenv("OLLAMA_MODEL", "").strip()
    ollama_ocr_base_url = (
        os.getenv("OLLAMA_OCR_BASE_URL", "").strip()
        or os.getenv("OLLAMA_BASE_URL", "").strip()
        or ollama_base_url
    )
    embedding_runtime = os.getenv("EMBEDDING_PYTHON", "")
    assets = {
        "ollama": {
            "configured": bool(ollama_base_url and ollama_model),
            "base_url": ollama_base_url,
            "model": ollama_model,
        },
        "unlimited_ocr": _path_status(
            os.getenv("UNLIMITED_OCR_MODEL_PATH", ""),
            os.getenv("UNLIMITED_OCR_PYTHON", ""),
        ),
        "ollama_ocr": {
            "configured": bool(
                ollama_ocr_base_url and os.getenv("OLLAMA_OCR_MODEL", "").strip()
            ),
            "base_url": ollama_ocr_base_url,
            "model": os.getenv("OLLAMA_OCR_MODEL", "").strip(),
        },
        "moss": _path_status(
            os.getenv("MOSS_MODEL_PATH", ""),
            os.getenv("MOSS_PYTHON", ""),
        ),
        "bge_m3": _path_status(os.getenv("BGE_M3_MODEL_PATH", ""), embedding_runtime),
        "nemotron": _path_status(
            os.getenv("NEMOTRON_EMBED_MODEL_PATH", ""),
            embedding_runtime,
        ),
    }
    return {
        "edition": edition,
        "configuration_mode": "environment" if edition == "roadshow" else "user",
        "locked": edition == "roadshow",
        "providers": {
            "llm": os.getenv("LLM_PROVIDER", "disabled"),
            "ocr": os.getenv("OCR_PROVIDER", "auto"),
            "audio": os.getenv("AUDIO_PROVIDER", "disabled"),
            "embedding": os.getenv("EMBEDDING_PROVIDER", "disabled"),
        },
        "assets": assets,
        "model_root": model_root_info(),
        "storage": public_storage_contract(),
    }
