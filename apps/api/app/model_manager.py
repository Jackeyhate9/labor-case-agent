from __future__ import annotations

import json
import hashlib
import os
import platform
import shutil
import subprocess
import threading
import urllib.request
import uuid
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .app_paths import app_data_root, application_home
from .services import ServiceError


@dataclass(frozen=True, slots=True)
class DownloadArtifact:
    url: str
    path: str
    sha256: str
    size: int


@dataclass(frozen=True, slots=True)
class ModelPack:
    id: str
    name: str
    capability: str
    description: str
    repo_id: str
    revision: str
    folder: str
    license: str
    model_bytes: int
    runtime_bytes: int
    runtime: str
    python_version: str
    hardware: str
    minimum_vram_gb: int
    source_url: str = ""
    license_url: str = ""
    dependency_summary: tuple[str, ...] = ()
    remote_code: bool = False
    recommended: bool = False
    requires_consent: bool = True
    artifacts: tuple[DownloadArtifact, ...] = ()


PACKS = (
    ModelPack(
        id="unlimited-ocr",
        name="智能长文档 OCR",
        capability="ocr",
        description="识别复杂聊天截图、长图和多栏文档；基础 OCR 已可用，此包用于提升质量。",
        repo_id="baidu/Unlimited-OCR",
        revision="2a06ebf2d6f600f95fd2b99f6ccdee18a52e3b8f",
        folder="Unlimited-OCR",
        license="MIT",
        model_bytes=6_778_368_291,
        runtime_bytes=6_500_000_000,
        runtime="unlimited-ocr",
        python_version="3.12",
        hardware="nvidia_gpu_required",
        minimum_vram_gb=12,
        source_url="https://huggingface.co/baidu/Unlimited-OCR",
        license_url="https://huggingface.co/baidu/Unlimited-OCR/blob/main/LICENSE",
        dependency_summary=("Python 3.12", "PyTorch 2.9 + CUDA 12.9", "Transformers 4.57.1"),
        remote_code=True,
    ),
    ModelPack(
        id="moss-transcribe-diarize",
        name="录音转写与说话人区分",
        capability="audio",
        description="把录音转换为带说话人和时间戳的文本。",
        repo_id="OpenMOSS-Team/MOSS-Transcribe-Diarize",
        revision="4a1af868018e7974197f4f018730758012b28c27",
        folder="MOSS-Transcribe-Diarize",
        license="Apache-2.0",
        model_bytes=1_833_163_110,
        runtime_bytes=6_000_000_000,
        runtime="moss-audio",
        python_version="3.12",
        hardware="nvidia_gpu_recommended",
        minimum_vram_gb=6,
        source_url="https://huggingface.co/OpenMOSS-Team/MOSS-Transcribe-Diarize",
        license_url="https://huggingface.co/OpenMOSS-Team/MOSS-Transcribe-Diarize/blob/main/LICENSE",
        dependency_summary=("Python 3.12", "PyTorch/Torchaudio 2.11 + CUDA 12.8", "MOSS runtime 40cf854"),
        remote_code=True,
        recommended=True,
    ),
    ModelPack(
        id="bge-m3",
        name="本地语义检索",
        capability="embedding",
        description="按语义查找已确认事实；可用 CPU，NVIDIA GPU 会更快。",
        repo_id="BAAI/bge-m3",
        revision="5617a9f61b028005a4858fdac845db406aefb181",
        folder="bge-m3",
        license="MIT",
        model_bytes=4_587_317_404,
        runtime_bytes=5_500_000_000,
        runtime="embedding",
        python_version="3.12",
        hardware="cpu_or_nvidia_gpu",
        minimum_vram_gb=4,
        source_url="https://huggingface.co/BAAI/bge-m3",
        license_url="https://huggingface.co/BAAI/bge-m3/blob/main/LICENSE",
        dependency_summary=("Python 3.12", "PyTorch 2.11", "Transformers 4.57.1"),
        recommended=True,
    ),
    ModelPack(
        id="nemotron-embed",
        name="高精度语义检索",
        capability="embedding",
        description="可替代 BGE-M3 的检索模型；只需选择一个语义模型。",
        repo_id="nvidia/Nemotron-3-Embed-1B-BF16",
        revision="a5e0f804b9e90a1ca6784ecbf6e41595774fc834",
        folder="Nemotron-3-Embed-1B-BF16",
        license="OpenMDW-1.1",
        model_bytes=2_299_031_578,
        runtime_bytes=5_500_000_000,
        runtime="embedding",
        python_version="3.12",
        hardware="nvidia_gpu_recommended",
        minimum_vram_gb=6,
        source_url="https://huggingface.co/nvidia/Nemotron-3-Embed-1B-BF16",
        license_url="https://huggingface.co/nvidia/Nemotron-3-Embed-1B-BF16/blob/main/LICENSE",
        dependency_summary=("Python 3.12", "PyTorch 2.11", "Transformers 4.57.1"),
    ),
)


@dataclass(frozen=True, slots=True)
class RuntimeProfile:
    id: str
    version: str
    python_version: str
    torch_index: str
    torch_packages: tuple[str, ...]
    packages: tuple[str, ...]


RUNTIME_PROFILES = {
    "unlimited-ocr": RuntimeProfile(
        id="unlimited-ocr",
        version="2026.07-cu129-v1",
        python_version="3.12",
        torch_index="https://download.pytorch.org/whl/cu129",
        torch_packages=("torch==2.9.0", "torchvision==0.23.0"),
        packages=(
            "transformers==4.57.1",
            "huggingface-hub==0.36.2",
            "hf-xet==1.4.2",
            "Pillow==12.1.1",
            "matplotlib==3.10.8",
            "einops==0.8.2",
            "addict==2.4.0",
            "easydict==1.13",
            "pymupdf==1.27.2.2",
            "psutil==7.2.2",
            "accelerate>=1.10,<2",
            "safetensors>=0.6,<1",
        ),
    ),
    "moss-audio": RuntimeProfile(
        id="moss-audio",
        version="2026.07-cu128-v1",
        python_version="3.12",
        torch_index="https://download.pytorch.org/whl/cu128",
        torch_packages=("torch==2.11.0", "torchaudio==2.11.0"),
        packages=(
            "transformers==4.57.1",
            "huggingface-hub==0.36.2",
            "hf-xet==1.4.2",
            "accelerate>=1.10,<2",
            "safetensors>=0.6,<1",
            "soundfile>=0.13,<1",
            "librosa>=0.11,<1",
            "https://github.com/OpenMOSS/MOSS-Transcribe-Diarize/archive/40cf8549c6b5634ba36b7e817cf523b5ad400c2e.zip",
        ),
    ),
    "embedding": RuntimeProfile(
        id="embedding",
        version="2026.07-cu128-v1",
        python_version="3.12",
        torch_index="https://download.pytorch.org/whl/cu128",
        torch_packages=("torch==2.11.0",),
        packages=(
            "transformers==4.57.1",
            "huggingface-hub==0.36.2",
            "hf-xet==1.4.2",
            "accelerate>=1.10,<2",
            "safetensors>=0.6,<1",
        ),
    ),
}

UV_VERSION = "0.11.28"
UV_BOOTSTRAP = DownloadArtifact(
    url=f"https://github.com/astral-sh/uv/releases/download/{UV_VERSION}/uv-x86_64-pc-windows-msvc.zip",
    path=f"uv-{UV_VERSION}-x86_64-pc-windows-msvc.zip",
    sha256="0a23463216d09c6a72ff80ef5dc5a795f07dc1575cb84d24596c2f124a441b7b",
    size=21_000_000,
)


def get_pack(pack_id: str) -> ModelPack:
    pack = next((item for item in PACKS if item.id == pack_id), None)
    if pack is None:
        raise ServiceError("MODEL_PACK_NOT_FOUND", "Unknown model capability pack", 404)
    return pack


def request_model_install(pack_id: str, *, accept_license: bool, accept_download: bool) -> dict[str, Any]:
    pack = get_pack(pack_id)
    if not accept_license or not accept_download:
        raise ServiceError(
            "MODEL_CONSENT_REQUIRED",
            "Confirm the model license and download size before installation",
            409,
        )
    capabilities = system_capabilities()
    gpu = capabilities["nvidia_gpu"]
    if pack.hardware == "nvidia_gpu_required" and (
        not gpu or int(gpu["memory_mib"]) < pack.minimum_vram_gb * 1024
    ):
        raise ServiceError(
            "MODEL_HARDWARE_INCOMPATIBLE",
            f"{pack.name} requires an NVIDIA GPU with at least {pack.minimum_vram_gb} GB VRAM",
            409,
        )
    runtime_needed = pack.runtime != "none" and not _runtime_python(pack).is_file()
    required = pack.model_bytes + (pack.runtime_bytes if runtime_needed else 0)
    required = int(required * 1.1) + 512 * 1024 * 1024
    if capabilities["disk_free_bytes"] < required:
        raise ServiceError(
            "MODEL_DISK_SPACE_INSUFFICIENT",
            f"At least {required} free bytes are required for this capability pack",
            409,
        )
    return _start_job(pack)


@dataclass(slots=True)
class InstallJob:
    id: str
    pack_id: str
    status: str
    phase: str
    downloaded_bytes: int
    total_bytes: int
    message: str
    error: str | None
    created_at: str
    updated_at: str
    cancel: threading.Event

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pack_id": self.pack_id,
            "status": self.status,
            "phase": self.phase,
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "message": self.message,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


_JOBS: dict[str, InstallJob] = {}
_JOB_LOCK = threading.RLock()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _update_job(job: InstallJob, **values: Any) -> None:
    with _JOB_LOCK:
        for key, value in values.items():
            setattr(job, key, value)
        job.updated_at = _now()


def _start_job(pack: ModelPack) -> dict[str, Any]:
    with _JOB_LOCK:
        existing = next(
            (job for job in _JOBS.values() if job.pack_id == pack.id and job.status in {"queued", "running"}),
            None,
        )
        if existing:
            return existing.public()
        timestamp = _now()
        job = InstallJob(
            id=str(uuid.uuid4()),
            pack_id=pack.id,
            status="queued",
            phase="preparing",
            downloaded_bytes=0,
            total_bytes=pack.model_bytes + pack.runtime_bytes,
            message="等待安装任务启动",
            error=None,
            created_at=timestamp,
            updated_at=timestamp,
            cancel=threading.Event(),
        )
        _JOBS[job.id] = job
    threading.Thread(target=_run_job, args=(job, pack), daemon=True, name=f"model-install-{pack.id}").start()
    return job.public()


def get_install_job(job_id: str) -> dict[str, Any]:
    with _JOB_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            raise ServiceError("MODEL_JOB_NOT_FOUND", "Model installation job not found", 404)
        return job.public()


def _safe_artifact_path(base: Path, relative: str) -> Path:
    target = (base / relative).resolve()
    if target != base and base not in target.parents:
        raise RuntimeError("model artifact path escapes the model directory")
    return target


def _download_artifact(job: InstallJob, artifact: DownloadArtifact, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    offset = partial.stat().st_size if partial.is_file() else 0
    headers = {"User-Agent": "LaborCaseAgent/0.2 model-manager"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(artifact.url, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        append = offset > 0 and getattr(response, "status", 200) == 206
        if not append:
            offset = 0
        mode = "ab" if append else "wb"
        with partial.open(mode) as output:
            while True:
                if job.cancel.is_set():
                    raise InterruptedError("installation cancelled")
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                offset += len(chunk)
                _update_job(
                    job,
                    downloaded_bytes=min(job.total_bytes, offset),
                    message=f"正在下载 {artifact.path}",
                )
    digest = hashlib.sha256()
    with partial.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest().lower() != artifact.sha256.lower():
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"SHA-256 verification failed for {artifact.path}")
    partial.replace(destination)


def _directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def _terminate_process_tree(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        process.terminate()


def _run_command(
    job: InstallJob,
    args: list[str],
    *,
    phase: str,
    message: str,
    monitor: Path | None = None,
    base_bytes: int = 0,
    byte_budget: int = 0,
) -> None:
    log_dir = runtime_root() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{job.id}.log"
    environment = os.environ.copy()
    environment.update(
        {
            "UV_CACHE_DIR": str(runtime_root() / "_cache"),
            "UV_PYTHON_INSTALL_DIR": str(runtime_root() / "_python"),
            "UV_PYTHON_BIN_DIR": str(runtime_root() / "_python-bin"),
            "UV_NO_PROGRESS": "1",
            "HF_HOME": str(model_root() / ".cache" / "huggingface"),
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "DO_NOT_TRACK": "1",
        }
    )
    _update_job(job, phase=phase, message=message)
    with log_path.open("ab") as log:
        process = subprocess.Popen(
            args,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=environment,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        while process.poll() is None:
            if job.cancel.wait(0.5):
                _terminate_process_tree(process)
                raise InterruptedError("installation cancelled")
            if monitor is not None and byte_budget:
                observed = min(byte_budget, _directory_size(monitor))
                _update_job(job, downloaded_bytes=min(job.total_bytes, base_bytes + observed))
    if process.returncode != 0:
        tail = ""
        try:
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-1000:].strip()
        except OSError:
            pass
        raise RuntimeError(tail or f"command failed with exit code {process.returncode}")


def _ensure_uv(job: InstallJob) -> Path:
    bootstrap = runtime_root() / "_bootstrap"
    uv_dir = bootstrap / f"uv-{UV_VERSION}"
    uv_path = uv_dir / ("uv.exe" if os.name == "nt" else "uv")
    if uv_path.is_file():
        return uv_path
    if os.name != "nt":
        raise RuntimeError("automatic runtime bootstrap is currently available for Windows only")
    archive = bootstrap / UV_BOOTSTRAP.path
    _update_job(job, phase="runtime_bootstrap", message="正在下载并校验隔离环境安装器")
    _download_artifact(job, UV_BOOTSTRAP, archive)
    uv_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            target = _safe_artifact_path(uv_dir.resolve(), member.filename)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
    if not uv_path.is_file():
        candidates = list(uv_dir.rglob("uv.exe"))
        if not candidates:
            raise RuntimeError("verified uv archive did not contain uv.exe")
        candidates[0].replace(uv_path)
    return uv_path


def _runtime_manifest_path(pack: ModelPack) -> Path:
    return runtime_root() / pack.runtime / ".labor-case-runtime.json"


def _ensure_runtime(job: InstallJob, pack: ModelPack) -> Path:
    if pack.runtime == "none":
        return Path()
    profile = RUNTIME_PROFILES[pack.runtime]
    python = _runtime_python(pack)
    manifest_path = _runtime_manifest_path(pack)
    gpu = system_capabilities()["nvidia_gpu"]
    backend = "cuda" if gpu else "cpu"
    desired_version = f"{profile.version}-{backend}"
    if python.is_file() and manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("version") == desired_version:
                _update_job(job, downloaded_bytes=min(job.total_bytes, pack.runtime_bytes))
                return python
        except (OSError, ValueError):
            pass

    uv = _ensure_uv(job)
    runtime = runtime_root() / pack.runtime
    runtime.mkdir(parents=True, exist_ok=True)
    _run_command(
        job,
        [str(uv), "venv", str(runtime), "--python", profile.python_version, "--managed-python", "--no-config"],
        phase="python_runtime",
        message=f"正在安装隔离 Python {profile.python_version}",
        monitor=runtime_root(),
        byte_budget=pack.runtime_bytes,
    )
    torch_index = profile.torch_index if gpu else "https://download.pytorch.org/whl/cpu"
    _run_command(
        job,
        [str(uv), "pip", "install", "--python", str(python), "--index-url", torch_index, *profile.torch_packages],
        phase="dependencies",
        message="正在安装 PyTorch 运行环境",
        monitor=runtime_root(),
        byte_budget=pack.runtime_bytes,
    )
    _run_command(
        job,
        [str(uv), "pip", "install", "--python", str(python), *profile.packages],
        phase="dependencies",
        message="正在安装模型依赖",
        monitor=runtime_root(),
        byte_budget=pack.runtime_bytes,
    )
    manifest_path.write_text(
        json.dumps(
            {
                "profile": profile.id,
                "version": desired_version,
                "python": profile.python_version,
                "torch_index": torch_index,
                "torch_packages": profile.torch_packages,
                "packages": profile.packages,
                "installed_at": _now(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _update_job(job, downloaded_bytes=min(job.total_bytes, pack.runtime_bytes))
    return python


def _download_snapshot(job: InstallJob, pack: ModelPack, python: Path) -> None:
    worker = Path(__file__).resolve().parent / "model_workers" / "download_snapshot.py"
    destination = model_root() / pack.folder
    _run_command(
        job,
        [
            str(python),
            str(worker),
            "--repo",
            pack.repo_id,
            "--revision",
            pack.revision,
            "--destination",
            str(destination),
        ],
        phase="model_download",
        message=f"正在下载 {pack.name}",
        monitor=destination,
        base_bytes=pack.runtime_bytes,
        byte_budget=pack.model_bytes,
    )


def _activate_pack(pack: ModelPack, python: Path) -> None:
    model = model_root() / pack.folder
    if pack.id == "unlimited-ocr":
        os.environ["UNLIMITED_OCR_MODEL_PATH"] = str(model)
        os.environ["UNLIMITED_OCR_PYTHON"] = str(python)
        patch = {"ocr_provider": "unlimited-ocr"}
    elif pack.id == "moss-transcribe-diarize":
        os.environ["MOSS_MODEL_PATH"] = str(model)
        os.environ["MOSS_PYTHON"] = str(python)
        patch = {"audio_provider": "moss-transcribe-diarize"}
    elif pack.id == "bge-m3":
        os.environ["BGE_M3_MODEL_PATH"] = str(model)
        os.environ["EMBEDDING_PYTHON"] = str(python)
        patch = {"embedding_provider": "bge-m3"}
    else:
        os.environ["NEMOTRON_EMBED_MODEL_PATH"] = str(model)
        os.environ["EMBEDDING_PYTHON"] = str(python)
        patch = {"embedding_provider": "nemotron-3-embed-1b"}
    from .settings import SystemSettingsPatch, save_settings

    save_settings(SystemSettingsPatch.model_validate(patch))


def _run_job(job: InstallJob, pack: ModelPack) -> None:
    try:
        _update_job(job, status="running", phase="downloading", message="准备下载模型文件")
        destination = model_root() / pack.folder
        destination.mkdir(parents=True, exist_ok=True)
        if pack.artifacts:
            downloaded = 0
            for artifact in pack.artifacts:
                _download_artifact(job, artifact, _safe_artifact_path(destination.resolve(), artifact.path))
                downloaded += artifact.size
                _update_job(job, downloaded_bytes=downloaded)
            manifest = {
                "pack_id": pack.id,
                "repo_id": pack.repo_id,
                "revision": pack.revision,
                "installed_at": _now(),
                "artifacts": [asdict(artifact) for artifact in pack.artifacts],
            }
            (destination / ".labor-case-pack.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            python = Path()
        else:
            python = _ensure_runtime(job, pack)
            _download_snapshot(job, pack, python)
            _activate_pack(pack, python)
        _update_job(
            job,
            status="completed",
            phase="ready",
            downloaded_bytes=job.total_bytes,
            message="模型与运行环境已安装",
        )
    except InterruptedError as exc:
        _update_job(job, status="cancelled", phase="cancelled", message=str(exc))
    except Exception as exc:
        _update_job(job, status="failed", phase="failed", error=str(exc), message="安装失败，可保留断点后重试")


def model_root_registry_path() -> Path:
    default = app_data_root() / "model-root.json"
    return Path(os.getenv("MODEL_ROOT_REGISTRY_FILE", default)).resolve()


def _model_files_present(model_dir: Path) -> bool:
    if not model_dir.is_dir():
        return False
    direct = (model_dir / "model.safetensors", model_dir / "pytorch_model.bin")
    return any(item.is_file() for item in direct) or any(model_dir.glob("model-*.safetensors"))


def _registered_model_root() -> Path | None:
    path = model_root_registry_path()
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        candidate = value.get("path") if isinstance(value, dict) else None
        return Path(candidate).resolve() if isinstance(candidate, str) and candidate else None
    except (OSError, ValueError):
        return None


def _environment_model_root_locked() -> bool:
    edition = os.getenv("APP_EDITION", "distribution").strip().lower()
    configuration_mode = os.getenv("APP_CONFIGURATION_MODE", "").strip().lower()
    explicitly_locked = os.getenv("MODEL_ROOT_MANAGED", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    return edition == "roadshow" or configuration_mode == "environment" or explicitly_locked


def model_root_info() -> dict[str, Any]:
    explicit = os.getenv("MODEL_ROOT", "").strip()
    if explicit and _environment_model_root_locked():
        return {
            "path": str(Path(explicit).resolve()),
            "source": "environment",
            "registration_allowed": False,
        }
    registered = _registered_model_root()
    if registered is not None:
        return {
            "path": str(registered),
            "source": "registered",
            "registration_allowed": True,
        }
    if explicit:
        return {
            "path": str(Path(explicit).resolve()),
            "source": "launcher_default",
            "registration_allowed": True,
        }
    return {
        "path": str((application_home() / "models").resolve()),
        "source": "default",
        "registration_allowed": True,
    }


def model_root() -> Path:
    return Path(model_root_info()["path"])


def register_model_root(path_value: str) -> dict[str, Any]:
    if os.getenv("MODEL_ROOT", "").strip() and _environment_model_root_locked():
        raise ServiceError(
            "MODEL_ROOT_MANAGED_BY_ENVIRONMENT",
            "MODEL_ROOT is managed by the launcher environment and cannot be replaced here",
            409,
        )
    candidate = Path(path_value)
    if not candidate.is_absolute():
        raise ServiceError("MODEL_ROOT_INVALID", "Model root must be an absolute local path", 422)
    if str(candidate).startswith(("\\\\", "//")):
        raise ServiceError("MODEL_ROOT_NETWORK_PATH_BLOCKED", "Network model roots are not accepted", 422)
    if not candidate.exists() or not candidate.is_dir():
        raise ServiceError("MODEL_ROOT_NOT_FOUND", "Model root directory does not exist", 404)
    if candidate.is_symlink():
        raise ServiceError("MODEL_ROOT_SYMLINK_BLOCKED", "Symbolic-link model roots are not accepted", 422)
    root = candidate.resolve()
    recognized = [pack.id for pack in PACKS if _model_files_present(root / pack.folder)]
    if not recognized:
        raise ServiceError(
            "MODEL_ROOT_EMPTY",
            "No recognized model capability folders were found in this directory",
            422,
        )
    registry = model_root_registry_path()
    registry.parent.mkdir(parents=True, exist_ok=True)
    temporary = registry.with_suffix(registry.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            {
                "path": str(root),
                "recognized_packs": recognized,
                "registered_at": _now(),
                "copied": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    temporary.replace(registry)
    return {
        "registered": True,
        "copied": False,
        "recognized_packs": recognized,
        "model_root": model_root_info(),
    }


def runtime_root() -> Path:
    default = model_root().parent / "runtimes"
    return Path(os.getenv("MODEL_RUNTIME_ROOT", default)).resolve()


def state_path() -> Path:
    default = app_data_root() / "model-manager.json"
    return Path(os.getenv("MODEL_MANAGER_STATE_FILE", default)).resolve()


def _load_state() -> dict[str, Any]:
    path = state_path()
    if not path.is_file():
        return {"onboarding_completed": False}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {"onboarding_completed": False}
    except (OSError, ValueError):
        return {"onboarding_completed": False}


def _save_state(value: dict[str, Any]) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def acknowledge_onboarding(choice: str) -> dict[str, Any]:
    if choice not in {"basic", "later", "installing"}:
        raise ServiceError("INVALID_ONBOARDING_CHOICE", "Unknown model onboarding choice", 422)
    state = _load_state()
    state.update(
        {
            "onboarding_completed": choice in {"basic", "installing"},
            "onboarding_choice": choice,
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )
    _save_state(state)
    return model_manager_status()


def _runtime_python(pack: ModelPack) -> Path:
    runtime = runtime_root() / pack.runtime
    return runtime / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _pack_locations(pack: ModelPack) -> tuple[Path, Path, bool]:
    environment_names = {
        "unlimited-ocr": ("UNLIMITED_OCR_MODEL_PATH", "UNLIMITED_OCR_PYTHON"),
        "moss-transcribe-diarize": ("MOSS_MODEL_PATH", "MOSS_PYTHON"),
        "bge-m3": ("BGE_M3_MODEL_PATH", "EMBEDDING_PYTHON"),
        "nemotron-embed": ("NEMOTRON_EMBED_MODEL_PATH", "EMBEDDING_PYTHON"),
    }
    names = environment_names.get(pack.id)
    if names is None:
        return model_root() / pack.folder, _runtime_python(pack), False
    model_name, runtime_name = names
    external_model = os.getenv(model_name, "").strip()
    external_runtime = os.getenv(runtime_name, "").strip()
    return (
        Path(external_model).resolve() if external_model else model_root() / pack.folder,
        Path(external_runtime).resolve() if external_runtime else _runtime_python(pack),
        bool(external_model or external_runtime),
    )


def _pack_status(pack: ModelPack) -> dict[str, Any]:
    model_dir, runtime_python, external = _pack_locations(pack)
    model_present = _model_files_present(model_dir)
    runtime_present = runtime_python.is_file()
    installed = model_present and runtime_present
    status = "ready" if installed else "runtime_missing" if model_present else "model_missing"
    return {
        **asdict(pack),
        "installed": installed,
        "status": status,
        "model_present": model_present,
        "runtime_present": runtime_present,
        "external": external,
        "model_path": str(model_dir),
        "runtime_path": str(runtime_python),
    }


def _nvidia_gpu() -> dict[str, Any] | None:
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    name, memory, driver = (part.strip() for part in completed.stdout.splitlines()[0].split(",", 2))
    return {"name": name, "memory_mib": int(memory), "driver": driver}


def system_capabilities() -> dict[str, Any]:
    root = model_root()
    root.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(root)
    gpu = _nvidia_gpu()
    return {
        "os": platform.system(),
        "architecture": platform.machine(),
        "disk_free_bytes": usage.free,
        "nvidia_gpu": gpu,
    }


def model_manager_status() -> dict[str, Any]:
    state = _load_state()
    packs = [_pack_status(pack) for pack in PACKS]
    return {
        "onboarding_required": not bool(state.get("onboarding_completed")),
        "automatic_downloads": False,
        "basic_mode": {
            "ready": True,
            "provider": "rapidocr",
            "description": "基础案件整理、文书和 CPU OCR 无需下载大型模型。",
        },
        "model_root": str(model_root()),
        "runtime_root": str(runtime_root()),
        "system": system_capabilities(),
        "packs": packs,
    }
