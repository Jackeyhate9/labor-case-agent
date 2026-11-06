from __future__ import annotations

import os
import threading
import ctypes
import time
from ctypes import POINTER, Structure, byref, c_char, c_void_p, cast, create_string_buffer
from ctypes.wintypes import BOOL, DWORD
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator, model_validator

from .app_paths import app_data_root
from .services import ServiceError
from .settings import effective_settings, load_settings


class StoredLLMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_url: str = ""
    model: str = ""


class LLMConfigPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_url: str | None = Field(default=None, max_length=2048)
    model: str | None = Field(default=None, max_length=200)
    api_key: SecretStr | None = Field(default=None, min_length=1, max_length=4096)
    clear_api_key: bool = False

    @model_validator(mode="after")
    def reject_conflicting_secret_actions(self) -> "LLMConfigPatch":
        if self.api_key is not None and self.clear_api_key:
            raise ValueError("api_key and clear_api_key cannot be supplied together")
        return self

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        return _normalize_base_url(value)

    @field_validator("model")
    @classmethod
    def normalize_model(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class LLMConnectionTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_url: str | None = Field(default=None, max_length=2048)
    model: str | None = Field(default=None, max_length=200)
    api_key: SecretStr | None = Field(default=None, min_length=1, max_length=4096)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        return _normalize_base_url(value)

    @field_validator("model")
    @classmethod
    def normalize_model(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


_LOCK = threading.RLock()
_DPAPI_DESCRIPTION = "Labor Case Agent LLM API key"
_CRYPTPROTECT_UI_FORBIDDEN = 0x1


class _DataBlob(Structure):
    _fields_ = [("cbData", DWORD), ("pbData", POINTER(c_char))]


def _normalize_base_url(value: str | None) -> str | None:
    if value is None:
        return value
    value = value.strip().rstrip("/")
    if not value:
        return ""
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url must be an absolute http(s) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("base_url cannot include credentials, query, or fragment")
    return value


def _blob_from_bytes(value: bytes) -> tuple[_DataBlob, Any]:
    buffer = create_string_buffer(value, len(value))
    return _DataBlob(len(value), cast(buffer, POINTER(c_char))), buffer


def _protect_secret(value: str) -> bytes:
    if os.name != "nt":
        raise ServiceError(
            "SECRET_STORAGE_UNAVAILABLE",
            "Persistent API key storage requires Windows DPAPI; use the LLM_API_KEY environment variable on this platform",
            503,
        )
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt32.CryptProtectData.argtypes = [
        POINTER(_DataBlob), c_void_p, c_void_p, c_void_p, c_void_p, DWORD, POINTER(_DataBlob)
    ]
    crypt32.CryptProtectData.restype = BOOL
    kernel32.LocalFree.argtypes = [c_void_p]
    kernel32.LocalFree.restype = c_void_p
    input_blob, input_buffer = _blob_from_bytes(value.encode("utf-8"))
    output_blob = _DataBlob()
    if not crypt32.CryptProtectData(
        byref(input_blob),
        _DPAPI_DESCRIPTION,
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        byref(output_blob),
    ):
        raise ServiceError("SECRET_STORAGE_FAILED", "Windows could not encrypt the API key", 500)
    try:
        return bytes(cast(output_blob.pbData, POINTER(c_char * output_blob.cbData)).contents)
    finally:
        kernel32.LocalFree(output_blob.pbData)
        del input_buffer


def _unprotect_secret(value: bytes) -> str:
    if os.name != "nt":
        raise ServiceError(
            "SECRET_STORAGE_UNAVAILABLE",
            "Persistent API key storage requires Windows DPAPI; use the LLM_API_KEY environment variable on this platform",
            503,
        )
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt32.CryptUnprotectData.argtypes = [
        POINTER(_DataBlob), c_void_p, c_void_p, c_void_p, c_void_p, DWORD, POINTER(_DataBlob)
    ]
    crypt32.CryptUnprotectData.restype = BOOL
    kernel32.LocalFree.argtypes = [c_void_p]
    kernel32.LocalFree.restype = c_void_p
    input_blob, input_buffer = _blob_from_bytes(value)
    output_blob = _DataBlob()
    if not crypt32.CryptUnprotectData(
        byref(input_blob),
        None,
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        byref(output_blob),
    ):
        raise ServiceError("SECRET_DECRYPTION_FAILED", "Windows could not decrypt the stored API key", 500)
    try:
        return bytes(cast(output_blob.pbData, POINTER(c_char * output_blob.cbData)).contents).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ServiceError("SECRET_DECRYPTION_FAILED", "Stored API key is invalid", 500) from exc
    finally:
        kernel32.LocalFree(output_blob.pbData)
        del input_buffer


def config_path() -> Path:
    path = Path(os.getenv("LLM_CONFIG_FILE", app_data_root() / "llm-config.json")).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def secret_path() -> Path:
    path = Path(os.getenv("LLM_SECRET_FILE", app_data_root() / "llm-secret.bin")).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_llm_config() -> StoredLLMConfig:
    path = config_path()
    with _LOCK:
        if not path.exists():
            return StoredLLMConfig()
        try:
            return StoredLLMConfig.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError, ValueError) as exc:
            raise ServiceError("LLM_CONFIG_CORRUPTED", "Persisted LLM configuration is invalid", 500) from exc


def save_llm_config(patch: LLMConfigPatch) -> StoredLLMConfig:
    with _LOCK:
        current = load_llm_config()
        values = current.model_dump()
        values.update(patch.model_dump(include={"base_url", "model"}, exclude_none=True))
        updated = StoredLLMConfig.model_validate(values)
        path = config_path()
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(updated.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)
        os.environ["LLM_BASE_URL"] = updated.base_url
        os.environ["LLM_MODEL"] = updated.model
        return updated


def save_api_key(api_key: str) -> None:
    ciphertext = _protect_secret(api_key)
    with _LOCK:
        path = secret_path()
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(ciphertext)
        temporary.replace(path)
        os.environ["LLM_API_KEY"] = api_key


def clear_api_key() -> None:
    with _LOCK:
        path = secret_path()
        if path.exists():
            path.unlink()
        os.environ.pop("LLM_API_KEY", None)


def load_api_key() -> str:
    from_environment = os.getenv("LLM_API_KEY")
    if from_environment:
        return from_environment
    path = secret_path()
    if not path.is_file():
        return ""
    return _unprotect_secret(path.read_bytes())


def public_llm_config() -> dict[str, Any]:
    stored = load_llm_config()
    settings = effective_settings(load_settings())
    base_url = os.getenv("LLM_BASE_URL", stored.base_url)
    model = os.getenv("LLM_MODEL", stored.model)
    api_key_configured = bool(os.getenv("LLM_API_KEY")) or secret_path().is_file()
    storage = "windows_dpapi" if os.name == "nt" else "environment_only"
    return {
        "provider": settings.llm_provider,
        "base_url": base_url,
        "model": model,
        "api_key_configured": api_key_configured,
        "storage": storage,
        "storage_available": os.name == "nt",
        "returned": False,
    }


def update_llm_config(patch: LLMConfigPatch) -> dict[str, Any]:
    if patch.api_key is not None:
        save_api_key(patch.api_key.get_secret_value())
    elif patch.clear_api_key:
        clear_api_key()
    save_llm_config(
        LLMConfigPatch(
            base_url=patch.base_url,
            model=patch.model,
        )
    )
    return public_llm_config()


def test_llm_connection(request: LLMConnectionTestRequest) -> dict[str, Any]:
    settings = effective_settings(load_settings())
    provider = settings.llm_provider
    cloud_provider = provider in {"openai-compatible", "deepseek-compatible", "qwen-compatible"}
    if settings.offline_mode and cloud_provider:
        raise ServiceError(
            "LLM_BLOCKED_BY_OFFLINE_MODE",
            "Cloud LLM connection tests are blocked while offline mode is enabled",
            409,
        )
    if provider == "disabled":
        raise ServiceError("LLM_PROVIDER_DISABLED", "Select an LLM provider before testing the connection", 409)

    stored = load_llm_config()
    base_url = request.base_url if request.base_url is not None else os.getenv("LLM_BASE_URL", stored.base_url)
    model = request.model if request.model is not None else os.getenv("LLM_MODEL", stored.model)
    api_key = request.api_key.get_secret_value() if request.api_key is not None else load_api_key()
    if not base_url:
        raise ServiceError("LLM_CONFIG_INCOMPLETE", "Base URL is required before testing the connection", 409)
    if cloud_provider and not api_key:
        raise ServiceError("LLM_CONFIG_INCOMPLETE", "API key is required before testing this provider", 409)

    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=10.0, follow_redirects=False) as client:
            response = client.get(f"{base_url}/models", headers=headers)
    except httpx.RequestError as exc:
        raise ServiceError(
            "LLM_CONNECTION_FAILED",
            "Could not reach the configured LLM service; verify the address and network",
            502,
        ) from exc
    latency_ms = max(0, round((time.perf_counter() - started) * 1000))
    if response.status_code in {401, 403}:
        raise ServiceError(
            "LLM_AUTHENTICATION_FAILED",
            "The LLM service rejected the API key",
            502,
        )
    if not response.is_success:
        raise ServiceError(
            "LLM_CONNECTION_FAILED",
            f"The LLM service returned HTTP {response.status_code}",
            502,
        )

    model_ids: list[str] = []
    try:
        payload = response.json()
        entries = payload.get("data", []) if isinstance(payload, dict) else []
        model_ids = [
            item["id"]
            for item in entries
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]
    except (ValueError, TypeError):
        model_ids = []
    return {
        "ok": True,
        "provider": provider,
        "base_url": base_url,
        "model": model,
        "model_available": model in model_ids if model and model_ids else None,
        "latency_ms": latency_ms,
        "message": "Connection successful",
    }
