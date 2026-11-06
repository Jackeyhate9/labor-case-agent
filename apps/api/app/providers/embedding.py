from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class EmbeddingConfiguration:
    provider: str
    model_version: str
    model_path: Path
    python_path: Path


def embedding_configuration() -> tuple[EmbeddingConfiguration | None, str]:
    provider = os.getenv("EMBEDDING_PROVIDER", "disabled").strip().lower()
    if provider == "disabled":
        return None, "disabled"
    if provider == "bge-m3":
        model_version = "bge-m3-v1"
        model_path = Path(os.getenv("BGE_M3_MODEL_PATH", ""))
    elif provider in {"nemotron", "nemotron-3-embed-1b"}:
        provider = "nemotron-3-embed-1b"
        model_version = "nemotron-v1"
        model_path = Path(os.getenv("NEMOTRON_EMBED_MODEL_PATH", ""))
    else:
        return None, "unknown_provider"
    python_path = Path(os.getenv("EMBEDDING_PYTHON", sys.executable))
    if not python_path.is_file():
        return None, "runtime_not_installed"
    if not model_path.is_dir():
        return None, "model_not_installed"
    if not any((model_path / name).is_file() for name in ("model.safetensors", "pytorch_model.bin")):
        return None, "model_weights_incomplete"
    return EmbeddingConfiguration(provider, model_version, model_path, python_path), "available"


def encode_texts(configuration: EmbeddingConfiguration, texts: list[str], role: str) -> list[list[float]]:
    worker = Path(__file__).resolve().parents[1] / "model_workers" / "embed_text.py"
    completed = subprocess.run(
        [
            str(configuration.python_path),
            str(worker),
            "--model",
            str(configuration.model_path),
            "--provider",
            configuration.provider,
            "--role",
            role,
        ],
        # ASCII escaping keeps the JSON pipe independent of the child process'
        # Windows console code page; json.load restores the original Unicode.
        input=json.dumps({"texts": texts}, ensure_ascii=True),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=int(os.getenv("EMBEDDING_TIMEOUT", "600")),
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip().splitlines()[-1:] or ["embedding worker failed"]
        raise RuntimeError(message[0])
    return json.loads(completed.stdout)["vectors"]
